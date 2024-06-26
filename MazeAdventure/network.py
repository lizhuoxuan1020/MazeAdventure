"""
功能：
    定义了能处理粘包、空缓冲区、满载缓冲区、数据残缺的收发函数send()和recv().
    定义了一个通用的小游戏网络服务器NetworkServer和网络客户端NetworkClient.
    （让不同的游戏可以复用该网络框架）
    NetworkServer:
        初始化：创建服务器socket,监听.
        主线程：不断连接新的客户端。
        线程：不断从每个客户端接收events，并立即更新game.
        线程：以固定频率更新game，并广播给所有客户端。
    NetworkClient:
        初始化：创建客户端socket.
        主线程：与服务器的连接、断开、重连。
        线程：向服务器发送events.
    备注：NetworkClient不应该实现interface的运行，而是interface中调用NetworkClient.
"""
import socket
import time
import threading
import copy
from pickle import loads,dumps
import selectors


def send(my_socket, data):
    """ 阻塞式发送数据: 以大端的方式，开头4个字节表示报文长度，后面跟着报文。"""
    message = dumps(data)
    message_length = len(message)
    # 字节流的前四个字节表示剩下有效字节流的长度。
    my_socket.sendall(message_length.to_bytes(4, 'big') + message)


def recv(my_socket):
    """ 阻塞式完整地接收一个数据包，且不考虑任何数据的缺失、错误，相信TCP. """
    # 阻塞式接收4个字节。
    size_needed = 4
    size_recv = 0
    bytes_recv = b""
    while size_recv < size_needed:
        bytes_recv += my_socket.recv(size_needed - size_recv)
        size_recv = len(bytes_recv)
    size_needed = int.from_bytes(bytes_recv, 'big')
    size_recv = 0
    bytes_recv = b""
    # 阻塞式接收剩下的数据。
    while size_recv < size_needed:
        bytes_recv += my_socket.recv(size_needed - size_recv)
        size_recv = len(bytes_recv)
    data = loads(bytes_recv)
    return data


class ThreadSafeList:
    """ 一个线程安全的列表 """
    '''
    修改与修改之间隔开，修改与读取之间隔开，读取与读取可以混合。
    这需要读写锁，Python中没有现成的读写锁，需要自己实现。读操作要有计数器。（这里略）
    '''
    def __init__(self, _list=None):
        if not _list:
            self.__list = []
        else:
            self.__list = copy.deepcopy(_list)
        self.lock = threading.Lock()

    def size(self):
        with self.lock:
            return len(self.__list)

    def empty(self):
        with self.lock:
            return len(self.__list)==0

    def append(self, *args):
        with self.lock:
            for arg in args:
                self.__list.append(arg)

    def update_whole(self, *args):
        with self.lock:
            self.__list.clear()
            for arg in args:
                self.__list.append(arg)

    def update(self, i, item_new):
        with self.lock:
            self.__list[i] = item_new

    def memset(self, item):
        with self.lock:
            for i in range(len(self.__list)):
                self.__list[i] = item

    def pop(self, item=-1, index=True):
        with self.lock:
            if index:
                if 0<=item<len(self.__list):
                    self.__list.pop(item)
            else:
                if item in self.__list:
                    self.__list.remove(item)

    def get(self, i):
        with self.lock:
            # 这里不要用deepcopy,因为socket等类型无法被序列化，会出错。
            return self.__list[i]

    def get_whole(self):
        with self.lock:
            # 这里不要用deepcopy,因为socket等类型无法被序列化，会出错。
            return self.__list

    def count(self, item):
        with self.lock:
            cnt = 0
            for val in self.__list:
                if val == item:
                    cnt+=1
            return cnt

    def all(self, item):
        with self.lock:
            for val in self.__list:
                if val != item:
                    return False
            return True

    def any(self, item):
        with self.lock:
            for val in self.__list:
                if val == item:
                    return True
            return False


class ThreadSafeVar:
    def __init__(self, _var=None):
        self.__var = _var
        self.lock = threading.Lock()

    def update(self, var_new):
        with self.lock:
            self.__var = var_new

    def get(self):
        with self.lock:
            return copy.deepcopy(self.__var)


class EventVar:
    def __init__(self):
        self.__var = None
        self.__event = threading.Event()

    def start(self):
        self.__event.wait()

    def handle(self, func, *args):
        # 处理
        func(*args, self.__var)
        # 重置event, 再次进入休眠，等待被唤醒。
        self.__event.clear()
        self.__event.wait()

    def update(self, _var_new):
        # 更新列表
        self.__var = _var_new
        # 唤醒处理线程。
        self.__event.set()

    def get(self):
        return self.__var


def get_host_ip():
    temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    temp_socket.connect(("8.8.8.8", 80))  # 连接到公共的 DNS 服务器
    local_ip = temp_socket.getsockname()[0]  # 获取本地 IP 地址
    return local_ip


"""
服务器与客户端的状态
*独立阶段
    服务器初始化，进入INITIATED状态，可以手动选择是否进行监听。
        调用match后，进入监听状态：MATCHING。
    客户端初始化，进入INITIATED状态，可以手动选择是否进行连接。
        调用connect后，进入连接状态：CONNECTING.
*互动阶段
    服务器一直处于MATCHING状态，并且对已连接的客户端创建广播线程，
        不断广播：自身状态+已连接的数量。
    客户端连接成功后，从CONNECTING状态进入CONNECTED状态，不断接收服务器发来的数量。
    服务器连接数量足够后，进入PREPARING状态。
        不断广播：自身状态+已就绪的id号。
    ---
    服务器就绪数量足够后，进入GAMING状态。
        不断广播：自身状态+game_status.
广播格式：
    长度校正码（4个固定字节），信息列表 [服务器状态，信息]
    拆解方式：先查看校正码，如果正确，就用list接收列表。
备注：主要的逻辑判断都在服务器，客户端是很被动的接收。
        单向广播通路必须一致敞开，且已固定频率发送，而不是只发送1次。
        服务器需要建立一个全局的消息队列，这样子线程发送的内容就可以变更！！
        客户端的状态不重要！！因为服务器不会去读取客户端的状态。客户端的状态就是服务器的状态。
    目前还没有服务器对客户端反馈的响应机制。
    当客户端断开等时，服务器会报错。
    
"""


class NetworkServer:
    """
    初始化：根据创建服务器socket，绑定ip和端口，激活监听参数。绑定游戏逻辑。

    主线程：不断连接新的客户端，加入到客户端列表中。或者从客户端列表中删除已经断开的连接。
    子线程：以固定频率更新game，并将game_status广播给所有客户端。
    子线程（n个，n为客户端数量）：不断从每个客户端接收events，并立即更新game.
            优化v2和v3：用select/epoll实现多路复用。
    """
    def __init__(self, server_address):
        self.address = server_address
        self.socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.socket.bind(self.address)
        self.socket.listen()
        self.client_sockets = ThreadSafeList()
        self.client_ready = ThreadSafeList([False for _ in range(self.max_clients)])

        self.freq = 60  # 服务器迭代game并广播的频率。
        self.lock = threading.Lock()
        self.counter = 0    # 服务器计数器。
        ''' 承载的游戏 '''
        self.game = None

        # self.send_cache_unique=[] 暂时不用写，对于策略类游戏，玩家间保持秘密的时候可以用。
        '''
        全局变量：服务器状态、消息列表
        服务器的状态：
            INITIATED,  初始化完成。
            MATCHING,   玩家人数不够，匹配玩家中。（即使客户端没有进行CONNECTING）
            PREPARING,  玩家人数足够，等待玩家确认开始。（或者一局游戏结束后等待玩家开始下一把）
            PLAYING,    游戏中。(包含游戏结束等)
        消息列表中存放要广播的信息。（不包含服务器状态和数据长度校验值）
        '''
        self.mode = ThreadSafeVar('INITIATED')
        # self.message_list = ThreadSafeList()
        print('服务器已创建，状态：INITIATED.')

    def bind(self, _game):
        self.game = _game

    def run(self):
        # 运行一开始就创建广播线程。
        threading.Thread(target=self.__thread_method_broadcast, name='broadcast').start()
        # 先进入MATCHING.
        self.mode.update('MATCHING')
        # 服务器在匹配、准备、游戏运行等状态间一直循环。
        while self.mode.get() != 'CLOSED':
            if self.mode.get() == 'MATCHING':
                self.__match()
            elif self.mode.get() == 'PREPARING':
                self.__prepare()
            elif self.mode.get() == 'PLAYING':
                self.__play()

    def __match(self):
        """
        连接新客户端直到客户端列表已满;
        所有新连接的客户端都得到一条广播通道，按固定频率广播全局变量消息列表。
        广播信息：self.mode, 已连接的client_socket列表。
        2023年12月5日00:44:53
        广播通道在一开始就有了，这里不需要创建。
        而是对于每一个客户端，创建一个接收即时数据的线程。
        """
        print('开始尝试处理客户端的连入，状态：MATCHING.')
        while self.client_sockets.size() < self.game.n_players:
            # 阻塞式等待并连接新客户端。
            n = self.client_sockets.size()
            client_socket = self.socket.accept()[0]
            print('新连入客户端：', client_socket)
            self.client_sockets.append(client_socket)
            # 更新消息列表为已连接客户端的列表。（这样客户端就能得到自己的id）
            # self.message_list.update_whole(self.client_sockets.get_whole())
            # 对于每一个客户端，创建一个接收即时数据并进行处理的线程。
            threading.Thread(target=self.__thread_method_recv,
                             args=(self.client_sockets.size()-1, client_socket),
                             name='recv_'+str(n)
                             ).start()
        # 连接数量足够，退出了while循环。
        # 先等待一小会儿，让客户端有时间处理id, 然后再修改状态值。
        time.sleep(2)
        self.mode.update('PREPARING')

    def __prepare(self):
        """
        重置self.client_ready.
        不断向所有客户端广播已就绪的客户端信息；
        被动等待每个客户端recv子线程对self.client_ready的修改，直到全部为True;
        注意！！！！：
            由于已经有了广播子线程，且子线程会自动固定频率广播全局变量信息列表，
            而每个客户端子线程也有了，会去修改全局变量客户端就绪列表。
            所以本函数唯一需要做的就是清空就绪列表，然后修改服务器状态。
        """
        print('玩家人数足够，正在等待每位玩家就绪，状态：PREPARING.')
        self.client_ready.memset(False)
        while self.client_ready.any(False): # 每隔N秒检测是否全部就绪。
            # 不断更改消息列表的值为就绪列表。

            time.sleep(0.1)
        # 先等待一小会儿，让客户端有时间处理, 然后再修改状态值。
        time.sleep(2)
        self.mode.update('PLAYING')

    def __play(self):
        """
        重置游戏。
        子线程（广播和接收）已经包揽了所有活。所以主线程就休眠，不去占用资源。
        """
        print('游戏开始，状态：PLAYING.')
        self.game.reset()
        while self.game.mode != 'QUIT':
            # 每N秒检查一次状态。
            time.sleep(2)
        # 游戏结束，如果人数足够就进入就绪状态，否则进入匹配阶段（比如有人返回主菜单，则应该断开该客户端）。
        self.mode.update('PREPARING')

    # 子线程方法：以固定频率更新服务器并向所有客户端广播全局变量中的内容。
    def __thread_method_broadcast(self):
        """ 广播的内容：[服务器状态，[消息列表的内容]]. """
        while self.mode.get() != 'QUIT':
            dt = 1.0 / self.freq
            client_sockets = self.client_sockets.get_whole()
            if not client_sockets:
                continue
            for i_client, client_socket in enumerate(client_sockets):
                if self.mode.get() == 'MATCHING':
                    send(client_socket, ['MATCHING', i_client])
                elif self.mode.get() == 'PREPARING':
                    send(client_socket, ['PREPARING', self.client_ready.get_whole()])
                # 游戏状态下，更新游戏，然后广播game_status.
                elif self.mode.get() == 'GAMING':
                    self.game.update_by_dt(dt)
                    send(client_socket, ['GAMING', self.game.get_status()])
            # 计数并print，便于调试。
            self.counter += 1
            if self.counter % 100 == 0:
                print('broadcast', 100, 'times.')
            time.sleep(dt)

    # 子线程方法（每个客户端套接字有一个）：接收客户端信息。若断开，从客户端列表中删除。
    def __thread_method_recv(self, i_client, client_socket):
        try:
            while True:
                # MATCHING阶段本线程被创建，但服务器能就地统计连接数量，故不接收信息。
                # PREPARING阶段，若接收到‘READY'开头的报文，就不断修改client_ready列表。
                data = recv(client_socket)
                if data:
                    print('msg from', i_client, data)
                    if self.mode.get() == 'PREPARING':
                        if data[0] == 'READY':
                            print('更新就绪列表')
                            self.client_ready.update(i_client, True)
                    # GAMING阶段，若接收到’GAMING'开头的报文，那么后面的部分就是actions.
                    elif self.mode.get() == 'GAMING':
                        if data and data[0] == 'GAMING':
                            actions = data[1]
                            self.game.update_by_actions(i_client, actions)
        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            # 客户端断开连接，移除它
            self.client_sockets.pop(client_socket, index=False)
            client_socket.close()

    """
    待升级（IO多路复用技术）：
    # 子线程方法：接收actions，更新游戏状态。(用select)
    def __thread_method_recv_v2(self, i_client, client_socket):
        return

    # 子线程方法：接收actions，更新游戏状态。(用epoll)
    def __thread_method_recv_v3(self, i_client, client_socket):
        return
    
    # 原子操作：对self.client_sockets进行增删。
    def __atomic_update_client_sockets(self,client_socket,mode):
        with self.lock:
            if mode.lower()=='add':
                if client_socket not in self.client_sockets:
                    self.client_sockets.append(client_socket)
            elif mode.lower()=='discard':
                if client_socket in self.client_sockets:
                    self.client_sockets.remove(client_socket)

    # 原子操作：对self.client_ready进行更改。
    def __atomic_update_client_ready(self,i_client,mode='flip'):
        with self.lock:
            if mode.lower()=='check':
                return all(self.client_ready)
            elif mode.lower()=='flip':
                self.client_ready[i_client] = True
            elif mode.lower()=='clear':
                for i in range(self.max_clients):
                    self.client_ready[i]=False

    def __broadcast(self,data,add_id=False):
        for i_client,client_socket in enumerate(self.client_sockets):
            if add_id:
                send(client_socket,data+'|'+str(i_client))
            else:
                send(client_socket,data)
    """


class NetworkClient:
    def __init__(self,server_host,server_port):
        self.server_host=server_host
        self.server_port=server_port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.id = None
        self.server_socket = None
        self.is_connected = False
        self.is_prepared = False

        # 几个全局变量,让子线程不断刷新这几个变量。其中events需要interface去刷新。
        # self.n_client_connected=None
        # self.clients_ready = None
        # self.game_status = None
        # self.events = None
        # 时时接收服务器状态
        # self.server_mode = ThreadSafeVar('INITIATED')
        # 接收数据列表(阻塞式即使接收)(第一个值永远是服务器的状态)
        self.message_list = ThreadSafeList()
        '''
        键盘鼠标事件，由外界刷新。但这里要注意几点：
            EventVar内置了event，有唤醒机制。
            内部的变量，即键盘鼠标事件本身，必须是可序列化的！！
        '''
        self.events = EventVar()

    def connect(self):
        """
        先创建接收信息的子线程，让其不断刷新全局变量。
        再主动连接服务器，获取id.
        """
        # 先创建接收数据的子线程。因为一旦连接成功后，服务器会以固定频率发来数据，撑爆缓冲区。
        threading.Thread(target=self.__thread_method_recv, name='client_recv').start()
        # 阻塞式连接。
        self.socket.connect((self.server_host, self.server_port))
        self.is_connected = True
        print('已连接至服务器')
        # 每隔N秒检查接收区，当接收到服务器MATCHING状态的数据后根据data计算本客户端id.
        while self.message_list.empty() or self.message_list.get(0) == 'INITIATED':
            print(self.message_list.get_whole())
            time.sleep(0.1)
        # 计算本机id.
        print('开始计算本机id')
        self.id = self.message_list.get(1)
        ''' 
        for i, client_socket in enumerate(client_sockets):
            if self.socket == client_socket:
                self.id = i
                '''
        print('本客户端id: ', self.id)

    def prepare(self):
        """
        主动向服务器每隔N秒发送一次‘READY’.
        被动不断接收来自服务器的关于就绪人数的广播。
        """
        print('本机已就绪')
        while self.message_list.empty() or self.message_list.get(0) != 'GAMING':
            # 注意这里要发送列表，以和后面的GAMING的报文的格式保持一致。
            send(self.socket, ['READY'])
            time.sleep(2)
        self.is_prepared = True
        print('本机和其他玩家已全部就绪，进入游戏。')

    def play(self):
        """ send events to server. """
        self.events.start()
        while self.message_list.empty() or self.message_list.get(0) != 'GAMEOVER':
            print('events updated and send:', self.events.get())
            self.events.handle(send, self.socket)
        print('本局游戏结束。')

    '''
    def __thread_method_send(self):
        """ send events to server. """
        while True:
            if self.events:
                # print('events: ', events)
                self.client.send(dumps(self.events))
    '''
    def __thread_method_recv(self):
        """ recv game_status from server. """
        # while self.is_connected:
        while True:
            if not self.is_connected:
                continue
            msg = recv(self.socket)
            if msg:
                server_mode, data = msg[0], msg[1]
                self.message_list.update_whole(server_mode, data)
                '''
                # 服务器正处于匹配状态，计算本客户端的id并不断刷新全局变量.
                if msg[0] == 'MATCHING':
                    client_sockets = msg[1]
                    for i, client_socket in enumerate(client_sockets):
                        if self.socket == client_socket:
                            self.id = i
                # 服务器正处于准备就绪状态，不断修改全局变量为发来的就绪列表.
                elif msg[0] == 'PREPARING':
                    self.clients_ready = msg[1]
                # 服务器正处于游戏状态，不断修改全局变量game_status.
                elif msg[0] == 'GAMING':
                    self.game_status = msg[1]
                    '''




