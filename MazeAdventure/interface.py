"""
功能：
    定义一个通用的客户端的UI界面。可以适用于不同的游戏。
"""
import pygame
import os
import threading
import asyncio

'''
def events_to_list(pygame_events):
    # 因为pygame.Event无法被序列化，使用起来不方便，所以转换成简易列表。
    # 这样也能剔除鼠标移动等这样的事件。
    # event.key, event.type等都是整型。
    # 所以，游戏中的单个event都是[type, key, ...]这样的列表形式。
    events = list()
    for event in pygame_events:
        event_list = [event.type]
        if event.type == pygame.QUIT:
            pass
        if event.type in [pygame.KEYDOWN, pygame.KEYUP]:
            event_list.append(event.key)
        if event.type in [pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP]:
            event_list.append(event.pos)
            event_list.append(event.button)
        events.append(event_list.copy())
    return events
'''


class Button(pygame.sprite.Sprite):
    def __init__(self, screen, pos, size, text, font, images):
        pygame.sprite.Sprite.__init__(self)
        # 按钮所在画布
        self.screen = screen
        # 按钮的位置,大小，以及被选中后放大多少倍。
        self.x, self.y = pos
        self.width, self.height = size
        self.rect = pygame.Rect([self.x, self.y, self.width, self.height])
        self.selected_expand = 1.1
        # 按钮上的文字
        self.text = text
        self.font = font
        # 按钮的图像(若被选中，按钮图像变大（可选）。)
        self.image_unselected = pygame.transform.scale(images[0],
                                                       [int(self.width), int(self.height)])
        self.image_selected = pygame.transform.scale(images[-1],
                                                     [int(self.width * self.selected_expand),
                                                      int(self.height * self.selected_expand)])

    def selected(self):
        pos = pygame.mouse.get_pos()
        if (self.x < pos[0] < self.x + self.width) \
                and (self.y < pos[1] < self.y + self.height):
            return True
        return False

    def draw(self):
        if not self.selected():
            self.screen.blit(self.image_unselected, [self.x, self.y])
        else:
            self.screen.blit(self.image_selected, [self.x-0.5*self.width*(self.selected_expand-1),
                                                   self.y-0.5*self.height*(self.selected_expand-1)])
        button_font = pygame.font.Font(self.font, int(0.7*self.height))  # 或者调用自己的字体  二者选其一
        button_font_surface = button_font.render(self.text, True, (0, 0, 50))
        text_rect = button_font_surface.get_rect(center=self.rect.center)
        self.screen.blit(button_font_surface, text_rect)


class Resources:
    """
    self.images = {'apple': [img0, img1,...], 'cat': [img0], ...}
    self.audios = {'apple': soundtrack0, ...}
    ...
    """
    def __init__(self):
        self.images = dict()
        self.audios = dict()
        self.fonts = dict()

    def load_from(self, obj, path):
        """ 将对象 obj 的所有多媒体材料加载到自己 """
        ''' load images '''
        if 'images' in obj.materials:
            for key in obj.materials['images']:
                self.images[key] = []
                for fname in os.listdir(path + 'images'):
                    fname_main, fname_extend = fname.split('.')
                    fkey = fname_main.split('_')[0]
                    if fkey == key:
                        self.images[key].append(pygame.image.load(path + 'images/' + fname))
        # 检查是否有对象自己提前生成的非加载图片。
        if hasattr(obj, 'selfmade_images'):
            for key, val_list in obj.selfmade_images().items():
                self.images[key] = val_list[:]
        ''' load audios '''
        if 'audios' in obj.materials:
            for key in obj.materials['audios']:
                for f in os.listdir(path+'audios'):
                    if f.split('.')[0] == key:
                        self.audios[key] = pygame.mixer.Sound(path + 'audios/' + f)
        ''' load fonts '''
        if 'fonts' in obj.materials:
            for key in obj.materials['fonts']:
                self.fonts[key] = path + 'fonts/' + key + '.ttf'
        ''' raise exceptions for missing materials '''
        materials_missing=[]
        if 'images' in obj.materials:
            for key,val in self.images.items():
                if not val:
                    materials_missing.append( 'Images_' + key)
        if 'audios' in obj.materials:
            for key,val in self.audios.items():
                if not val:
                    materials_missing.append('Audios_' + key)
        if 'fonts' in obj.materials:
            for key,val in self.fonts.items():
                if not val:
                    materials_missing.append('Fonts_' + key)
        if materials_missing:
            msg_e='材料缺失：'+','.join(materials_missing)
            raise Exception(msg_e)
        else:
            print('材料加载完毕')


class Interface:
    """ 通用的界面 """
    ''' 菜单按钮 '''
    BUTTONS = {
        'CONNECTING_ONLINE': '开始游戏[在线]',
        'GAMING_LOCAL': '开始游戏[单机]',
        'RECORDS': '对局记录',
        'SETTINGS': '设置',
        'INFOMATION': '制作信息',
        'QUIT': '退出'
    }
    ''' 界面状态 (列在这里主要为了提醒状态有哪些)'''
    MODES = [
        'MENU',
        'CONNECTING_ONLINE', 'PREPARING_ONLINE', 'GAMING_ONLINE', 'GAMEOVER_ONLINE',
        'GAMING_LOCAL', 'GAMEOVER_LOCAL',
        'RECORDS',
        'SETTINGS',
        'INFORMATION',
        'QUIT'
    ]

    def __init__(self, game):
        pygame.init()
        pygame.mixer.init()
        self.mode = 'MENU'
        self.game = game      # 必须绑定。
        self.client = None    # 可选择绑定。
        ''' 根据游戏自带的显示区域大小，确定界面大小。（暂略：从设置中读取 self.height） '''
        self.H = 770
        #self.H = 300
        self.W = int(self.H * self.game.width_height_ratio)
        self.size = [self.W, self.H]
        self.screen = pygame.display.set_mode([self.W, self.H])
        self.materials={
            'images': ['MENU', 'SETTINGS', 'CONNECTING', 'PREPARING',
                       'button'],
            'audios': ['MENU',
                       'buttonSelected', 'buttonClicked', 'GAMEOVER'],
            'fonts': ['times','simhei']
        }
        ''' 加载界面和游戏的所有多媒体材料 '''
        self.path = 'resources/'
        self.resources = Resources()
        self.resources.load_from(self, self.path)
        self.game(self.resources.load_from, path=self.path)
        ''' 界面帧率 '''
        self.events = []
        self.FPS = 60
        self.clock = pygame.time.Clock()
        self.frame = 0  # 帧序号，用于绘制动画。
        self.MOD = 99999999

    def bind_network(self, client):
        self.client = client

    def run(self):
        while self.mode != 'QUIT':
            # print('当前状态：',self.mode, threading.current_thread().ident)
            # handle events of keyboard and mouse.
            if self.mode == 'MENU':
                self.__run_menu()
            elif self.mode == 'SETTINGS':
                self.__run_settings()
            elif self.mode == 'CONNECTING_ONLINE':
                self.__run_connect_online()
            elif self.mode == 'PREPARING_ONLINE':
                self.__run_prepare_online()
            elif self.mode == 'GAMING_ONLINE':
                self.__run_game_online()
            elif self.mode == 'GAMING_LOCAL':
                self.__run_game_local()
            elif self.mode == 'INFORMATION':
                self.__run_information()

    def __run_menu(self):
        # 循环播放菜单界面的背景音乐。
        self.resources.audios['MENU'].play(-1)
        while self.mode == 'MENU':
            # 菜单界面的背景图片。
            self.screen.fill((0, 0, 0))
            surf_menu = pygame.transform.scale(self.resources.images['MENU'][0], self.size)
            self.screen.blit(surf_menu, [0, 0])
            # 菜单界面的按钮。
            bw, bh = self.W * 0.2, self.H * 0.05
            ew, eh = self.W * 0.6, self.H * 0.2
            click = ''
            for i,btn in enumerate(Interface.BUTTONS.keys()):
                button = Button(self.screen, [ew, eh + bh * i * 2], [bw, bh],
                                Interface.BUTTONS[btn], self.resources.fonts['simhei'],
                                self.resources.images['button'])
                button.draw()
                if button.selected():
                    click=btn
            # 是否点击按钮。
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.mode = 'QUIT'
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if click:
                        self.mode=click
            pygame.display.flip()
            self.clock.tick(self.FPS)
        # 停止播放菜单界面的背景音乐。
        self.resources.audios['MENU'].stop()

    def __run_settings(self):
        i_image = 0
        while self.mode == 'SETTINGS':
            self.screen.fill((0, 0, 0))
            self.screen.blit(self.resources.images['SETTINGS'][i_image], [0, 0])
            i_image = (i_image + 1) % len(self.resources.images['SETTINGS'])
            pygame.display.flip()
            self.clock.tick(self.FPS)

    def __run_connect_online(self):
        # 子线程：让self.game_client连接到self.game_server.
        threading.Thread(target=self.client.connect).start()
        # 主线程：循环播放网络连接界面的背景图片。
        i_image = 0
        while not self.client.is_connected:
            self.screen.fill((0, 0, 0))
            surf_conn = pygame.transform.scale(self.resources.images['CONNECTING'][i_image],
                                               self.size)
            self.screen.blit(surf_conn, [0, 0])
            i_image=(i_image+1)%len(self.resources.images['CONNECTING'])
            pygame.display.flip()
            self.clock.tick(self.FPS)
        self.mode = 'PREPARING_ONLINE'

    def __run_prepare_online(self):
        # 主线程：就绪界面，包含一个准备按钮和一个退出按钮。
        # 开始播放就绪界面的BGM（用主菜单BGM代替）。
        self.resources.audios['MENU'].play(-1)
        prepare_clicked = False # 就绪按钮只需要按一次。
        print('interface: 进入preparing循环。')
        while not self.client.is_prepared:
            self.screen.fill((0, 0, 0))
            surf_prep = pygame.transform.scale(self.resources.images['PREPARING'][0],
                                               self.size)
            self.screen.blit(surf_prep, [0, 0])
            # 绘制所有玩家的头像。就绪玩家头像下面有“已准备”的字样。
            client_recv = self.client.message_list.get_whole()
            # print('interface: client收到的信息：',client_recv)
            if client_recv and client_recv[0] == 'PREPARING':
                prep_info = client_recv[1]
                # print('interface: client中的prep info：', prep_info)
                n = len(prep_info)
                w = int(0.2*self.size[0])
                h = int(0.3*self.size[1])
                gap_x = 1.2*w
                gap_y = 0.1*h   # 头像下沿与准备之间的空隙。
                x0 = (self.size[0] - n*w -(n-1)*gap_x)/2
                y0 = 0.3*self.size[1]
                for i,val in enumerate(prep_info):
                    # 绘制每位玩家的头像。
                    x = x0 + i*(w + gap_x)
                    y = y0
                    # 头像和边框
                    self.screen.blit(pygame.transform.scale(self.resources.images['profile'][0],
                                                     [w, h]), [x, y])
                    pygame.draw.rect(self.screen, [100, 100, 0], [x, y, w, h], 2)
                    # 如果这是你自己，那么用绿框标出。
                    if i == self.client.id:
                        pygame.draw.rect(self.screen, [50, 100, 50], [x, y ,w,h], 3)
                    # 若已准备，则下方显示已准备（不论是否是自己）。
                    th = int(h * 0.2)
                    if val:
                        text = '已准备'
                        font = pygame.font.Font(self.resources.fonts['simhei'], th)
                        text_surface = font.render(text, True, (255, 200, 255))
                        self.screen.blit(text_surface, [x, y+h+gap_y])
                    # 若未准备，对于其他人什么都不绘制，对于自己绘制一个就绪按钮。
                    elif i == self.client.id:
                        # 就绪按钮
                        btn = Button(self.screen, [x, y+h+gap_y], [w, th], '准备',
                                     self.resources.fonts['simhei'],
                                     self.resources.images['button'])
                        btn.draw()
                        # 判断玩家的点击
                        for event in pygame.event.get():
                            if event.type == pygame.QUIT:
                                self.mode = 'QUIT'
                            if event.type == pygame.MOUSEBUTTONDOWN:
                                # 若鼠标点击到准备按钮，就让客户端准备（启动子线程）。
                                if btn.selected() and not prepare_clicked:
                                    print('已经点击就绪。')
                                    threading.Thread(target=self.client.prepare).start()
                                    prepare_clicked = True
                                    # 当客户端状态变为游戏中时，退出该函数进入游戏函数。
            pygame.display.flip()
            self.clock.tick(self.FPS)
        print('Interface进入游戏啦')
        self.mode = 'GAMING_ONLINE'
        # 停止播放就绪界面的BGM。
        self.resources.audios['MENU'].stop()

    def __run_game_online(self):
        # 子线程：让self.game_client不断获取广播，并发送events.
        threading.Thread(target=self.client.play, name='client_send').start()

        # 主线程：游戏渲染，并时时给客户端网络传去动作列表。
        while self.mode == 'GAMING_ONLINE':
            self.screen.fill((0, 0, 0))
            self.game.draw_and_act(self.screen, self.client.message_list.get_whole()[1],
                                   self.resources, self.frame, self.client.id)
            # 如果game有用户操作，就让客户端发送。
            if self.game.actions:
                self.client.events.update(['GAMING', self.game.actions])
            pygame.display.flip()
            if self.game.mode == 'GAMEOVER':
                self.mode = 'GAMEOVER_ONLINE'
            # 帧率
            self.frame = (self.frame + 1) % self.MOD
            self.clock.tick(self.FPS)

    def __run_game_local(self):
        self.game.reset(n_players=1)
        while self.mode == 'GAMING_LOCAL':
            self.screen.fill((0, 0, 0))
            self.game.update_by_actions(0, self.game.actions)
            self.game.update_by_dt(1/self.FPS)
            self.game.draw_and_act(self.screen, self.game.get_status(),
                                   self.resources, self.frame)
            pygame.display.flip()
            if self.game.mode == 'GAMEOVER':
                self.mode = 'GAMEOVER_LOCAL'
            # 帧率
            self.frame = (self.frame+1) % self.MOD
            self.clock.tick(self.FPS)

    def __run_information(self):
        pass


if __name__ == '__main__':
    interface=Interface([1000,700],1)
    interface.run()