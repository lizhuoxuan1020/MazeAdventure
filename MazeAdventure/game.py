"""
功能：
    定义游戏的基本逻辑。
"""
import pygame
import random
import numpy as np
import threading
import os
import queue
import copy


class Map:
    """ 地图 'ROAD':1,'WALL':0 """
    def __init__(self, rows_road, cols_road, width, density=0.97):
        """ 矩阵的奇数列和行表示格挡物，偶数列和行表示可行地块。最外层为格挡物。 """
        self.rows_road = rows_road  # 可行地块的行数。
        self.cols_road = cols_road  # 可行地块的列数。
        self.rows = rows_road * 2 + 1
        self.cols = cols_road * 2 + 1
        ''' 地图的0-1矩阵 '''
        self.maze = np.zeros((self.rows, self.cols), dtype=int)
        ''' 地图上的物体容器(由外界进行初始化或更改) '''
        self.objects = [[[] for _ in range(self.cols)] for _ in range(self.rows)]
        ''' 地图上的标记容器(由外界进行初始化或更改) '''
        self.marks = [[[] for _ in range(self.cols)] for _ in range(self.rows)]
        ''' 地图生成 '''
        self.__generate_by_prim()
        self.__simplify(density=density)
        self.width = width  # 路宽。
        ''' 多媒体材料（用于客户端和本地） '''
        self.materials = {'images': ['wall', 'road']}

    def __get_neighbors(self,r,c,val):
        """ get neighbors which value equals val. """
        neighbors = set()
        for dir in [[2, 0], [0, 2], [-2, 0], [0, -2]]:
            rn, cn = r + dir[0], c + dir[1]
            if 0 <= rn < self.rows and 0 <= cn < self.cols and self.maze[rn, cn] == val:
                neighbors.add((rn,cn))
        return neighbors

    def __generate_by_prim(self):
        """ generate matrix using random prim algorithm. """
        r_start = random.randint(0, self.rows_road - 1)*2+1
        c_start = random.randint(0, self.cols_road - 1)*2+1
        frontiers=set()
        frontiers.add((r_start,c_start))
        while frontiers:
            # 第一步：当前树的周围集frontiers中随机找到一个节点，并接纳该节点到当前树。
            r,c = random.choice(list(frontiers))
            self.maze[r, c] = 1
            # 第二步：该节点可能和当前树有多个边相连，随机选择其中一个边并连通。
            edges=self.__get_neighbors(r,c,1)
            if edges:
                rp,cp= random.choice(list(edges))
                self.maze[(r+rp)//2,(c+cp)//2]=1
            # 第三步：将该节点的周围节点加入到周围集frontiers中，并把该节点从frontier删除。
            frontiers=frontiers.union(self.__get_neighbors(r,c,0))
            frontiers.remove((r,c))

    def __simplify(self, density=1.0):
        """
                function: simplify maze by changing some walls to paths.
                density means density of inner walls, where 0.0 means no wall.
        """
        # 对于一棵树，内墙单元的个数=外墙内部总单元个数-最小生成树的节点和边的个数总和。
        n_inner_walls=(self.rows-2)*(self.cols-2)-(self.rows_road*self.cols_road*2-1)
        n_inner_walls_remove=int((1-density)*n_inner_walls)
        while n_inner_walls_remove:
            # r=random.randint(0,self.rows-2)*2+2 错！这样会漏掉大量的墙。
            r = random.randint(1, self.rows-2)
            c = random.randint(1, self.cols-2)
            # 若该单元为墙，且不是角落。
            if self.maze[r,c]==0 and (self.maze[r-1,c]==self.maze[r+1,c]==1
                                      or self.maze[r,c-1]==self.maze[r,c+1]==1):
                self.maze[r,c]=1
                n_inner_walls_remove-=1

    def calc_path(self, pos_a, pos_b):
        """ calc shortest path between A and B using bfs. """
        rA,cA=pos_a
        rB,cB=pos_b
        if self.maze[rA][cA]==0 or self.maze[rB][cB]==0:
            return []
        nrows,ncols=self.rows,self.cols
        path=[]
        visited=[[False]*ncols for _ in range(nrows)]
        parent=[[None]*ncols for _ in range(nrows)]
        q=queue.Queue()
        q.put([rA,cA])
        visited[rA][cA] = True
        while not q.empty():
            r,c=q.get()
            if [r,c]==[rB,cB]:
                break
            for direct in [[-1,0],[1,0],[0,-1],[0,1]]:
                rn,cn=r+direct[0],c+direct[1]
                if 0<=rn<nrows and 0<=cn<ncols and self.maze[rn][cn]==1 and not visited[rn][cn]:
                    q.put([rn,cn])
                    parent[rn][cn]=[r,c]
                    visited[rn][cn] = True
        r,c=rB,cB
        while parent[r][c]:
            path.append([r,c])
            r,c=parent[r][c]
        path.append([rA,cA])
        path=path[::-1]
        return path

    def valid_area(self, *args):
        """ judge if an area can be placed in roads """
        # 矩形像素块
        if args[0] == 'rect':
            x, y, w, h = args[1]
            r_min = max(0, int(y/self.width))
            r_max = min(self.rows-1, int((y+h)/self.width))
            c_min = max(0, int(x / self.width))
            c_max = min(self.cols-1, int((x+w) / self.width))
            for r in range(r_min, r_max+1):
                for c in range(c_min, c_max+1):
                    if self.maze[r][c] <= 0:
                        return False
            return True
        # 矩阵下标列表
        elif args[0] == 'indices':
            indices = args[1]
            for r,c in indices:
                if self.maze[r][c] <= 0:
                    return False
            return True

    def print(self):
        """ print self.matrix. """
        for rows in self.maze:
            for elem in rows:
                print(elem,end=' ')
            print(end='\n')

    def plot(self,path=None,save_name='noname'):
        """ plot self.matrix. """
        pygame.init()
        w= 2000
        h=int((self.rows_road/self.cols_road)*w)
        ew,eh= 20,20
        color_background=[100,100,100]
        color_wall=[0,0,0]
        color_road = [255, 255, 255]
        color_path =[0,255,0]
        color_path_start,color_path_end=[255,0,0],[0,0,255]
        screen = pygame.display.set_mode((w+2*ew, h+2*eh))
        screen.fill(color_background)
        pygame.draw.rect(screen,color_wall,(ew, eh, w, h))
        cw,ch=w/self.cols,h/self.rows
        for r in range(self.rows):
            for c in range(self.cols):
                if self.maze[r, c] == 1:
                    pygame.draw.rect(screen, color_road,(ew+cw*r,eh+ch*c,cw+1,ch+1))
        pygame.image.save(screen, save_name + ".png")
        for i in range(len(path)):
            r,c=path[i]
            color=color_path
            if i==0:
                color=color_path_start
            if i==len(path)-1:
                color=color_path_end
            pygame.draw.rect(screen, color, (ew + cw * r, eh + ch * c, cw +1, ch +1))
        pygame.image.save(screen, save_name+"_solved.png")
        return


class Explorer(pygame.sprite.Sprite):
    def __init__(self, pos, size):
        pygame.sprite.Sprite.__init__(self)
        ''' 人物中心位置的坐标 '''
        self.x, self.y = pos
        self.pos = [self.x, self.y]
        ''' 尺寸，矩形。'''
        self.SIZE_MAX = size
        self.size = self.SIZE_MAX[:]
        self.width, self.height = self.size
        self.rect = pygame.rect.Rect([int(self.x-self.width/2),int(self.y-self.height/2),
                                      self.width,self.height])
        ''' 人物的当前方向(left, right, up, down 四个方向是否被激活)、当前速率，固定最大速度(不可变) '''
        self.direction = [0, 0, 0, 0]
        self.V_MAX = [300, 300]
        self.v = self.V_MAX[:]
        ''' 新增：面朝向。方便绘图，且可以用于石化等互动。 '''
        self.facial_orientation = 0
        ''' 视野范围 field of view '''
        self.fov = 100
        self.FOV_MAX = 100
        ''' 动作范围/拾取范围 (不应该是固定值，而是和人物尺寸相关。) '''
        self.act_scale = 1.20
        ''' 背包：装延迟使用的物品。 '''
        self.bag_capacity=10
        self.bag=[None for _ in range(self.bag_capacity)]
        ''' 水晶碎片拾取个数 '''
        self.crystals_found = dict()
        ''' 所受效果列表。对于每个效果：[类型名称，所剩时间]，用dt相减。 '''
        self.effects = []
        ''' 图像和音轨（仅在客户端或本地会被调用） '''
        self.materials = {'images': ['explorerUp','explorerDown',
                                     'explorerLeft','explorerRight']}

    def next_pos(self, dt):
        """ 根据当前的移动方向，计算下一步可能的位置 """
        diag_nerf = 1.0
        lf, r, u, d = self.direction
        dx = r - lf
        dy = d - u
        # 如果两个方向同时移动，对角线的速度需要除以根号2.
        if dx*dy != 0:
            diag_nerf = 1.414
        xn = self.x + dx * self.v[0] * dt/diag_nerf
        yn = self.y + dy * self.v[1] * dt/diag_nerf
        return [xn, yn]

    def update_direction(self, i_dir, val):
        """ 根据新的动作，来更新人物的运动向量和朝向 """
        '''
        这里仔细想一想！！ 目标是：人物移动时有方向，静止时也有方向。
            所以，所谓移动，就是在所在方向上的移动。
        最后想出的办法：
            先保留原先的面朝向。
            任何让direction变为非零的操作，都要重新定向。
            否则，保留原来的朝向。        
        '''
        self.direction[i_dir] = val
        # 计算面部朝向，如果在单向移动那么很好算，如果静止则不变，如果多向移动则以先动的那个方向为准。
        lf, r, u, d = self.direction
        if lf == r and (u != d):
            self.facial_orientation = 2 if u else 3
        elif lf != r and (u == d):
            self.facial_orientation = 0 if lf else 1
        elif lf != r and (u != d):
            if i_dir <= 1:
                self.facial_orientation = 2 if u else 3
            else:
                self.facial_orientation = 0 if lf else 1

    def update_pos(self, pos):
        self.pos[0] = pos[0]
        self.pos[1] = pos[1]

    def update_bag(self, *args, mode='add'):
        """ 尝试添加或删除或交换背包中的物体 """
        if mode == 'remove':
            self.bag[args[0]] = None
            return True
        elif mode == 'add':
            # 从头到尾寻找空位，找到即可加入。否则返回False.
            for i in range(self.bag_capacity):
                if self.bag[i] is None:
                    self.bag[i] = args[0]
                    return True
            return False
        elif mode == 'swap':
            # 交换两个物体的位置（包括空位）。
            i, j =args
            tmp = self.bag[i]
            self.bag[i] = self.bag[j]
            self.bag[j] = tmp
            return True
        elif mode == 'expand':
            self.bag_capacity += args[0]
            for i in range(args[0]):
                self.bag.append(None)
            return True
        return False

    def update_effects(self, *args, mode='update'):
        """ 添加或更新effects列表，effect就是object!! """
        # 如果不存在这个effect，就添加，否则就延长作用时间。
        if mode == 'add':
            print('尝试添加effect ')
            obj = args[0]
            print('obj ', obj)
            ith = 0
            while ith < len(self.effects):
                if self.effects[ith].name == obj.name:
                    break
                ith += 1
            if ith == len(self.effects):
                self.effects.append(obj)
            else:
                self.effects[ith].t += obj.t
        # 减dt所有的effects，删除过期的并释放其反向作用。
        elif mode == 'update':
            dt = args[0]
            _map = args[1]
            ith = 0
            while ith < len(self.effects):
                self.effects[ith].t -= dt
                if self.effects[ith].t <= 0:
                    self.effects[ith].use(self, _map,'recover')
                    print('效果结束：', self.effects)
                    self.effects.pop(ith)
                else:
                    ith += 1


class Object(pygame.sprite.Sprite):
    INFO = {
        'lemon': ['一颗酸酸的柠檬','眼睛好干。'],
        'watermelon': ['一个大西瓜','大西瓜能缩小体型，很合理吧。'],
        'apple': ['一颗红红的苹果','跑快快！'],
        #
        'snowflake': ['一大片雪花','冻结！'],
        'coffee': ['一杯香甜的热咖啡','驱散一切效果，打起精神来！'],
        'mushroom': ['一朵毒蘑菇','好晕~'],
        #
        'crystalScarlet': ['赤炎（红宝石）',''],
        'crystalBlue': ['星辰（蓝宝石）',''],
        'crystalGreen': ['翡翠（绿宝石）',''],
        'crystalYellow': ['秋辉（黄宝石）',''],
        #
        'shovel': ['一把洛阳铲',''],
        'hammer': ['一把雷霆之锤',''],
        'mark': ['一个地图标记',''],
        'cat': ['小猫咪', '喵~ 我能发现宝石。'],
        'dog': ['小狗','我的嗅觉很灵敏。'],
        'crayon': ['蜡笔', '标记地图，记得回头路。'],
        'balloon': ['气球', '飘起来，克服障碍！']
    }
    ID_CUR = 0

    def __init__(self, name, pos, size, depreciation=100):
        pygame.sprite.Sprite.__init__(self)
        ''' 给每一个物品都赋予一个独一无二的id，防止物品的位置属性等一样时发生判断困难。'''
        self.id = Object.ID_CUR
        Object.ID_CUR += 1
        self.name = name
        ''' 中心位置和尺寸'''
        self.x, self.y = pos
        self.size = size
        ''' 使用总寿命为100，,当前使用寿命和每次的损耗。 '''
        self.life_span = 100
        self.depreciation = depreciation
        ''' 效果名称和持续时间 '''
        self.effect_name = ''
        self.t = 99999999.0
        ''' 图像和音轨（仅在客户端或本地会被调用） '''
        self.materials = {'images': [name]}

    # 重载比较符。
    def __eq__(self, other):
        if isinstance(other, Object):
            return self.id == other.id
        return False

    def pick(self, explorer):
        pass

    def use(self, explorer, _map, mode='apply'):
        """
        使用后，效果分两种：直接永久改变，限时BUFF（持续一段时间，多为负面效果）.
        相同BUFF不能叠加效果，但可以延长持续时间。
        mode = apply or recover.
        """
        print('被使用 ', self.name)
        # 永久改变(不会有recover的调用)。
        if self.name == 'coffee':
            '''   咖啡产生直接永久效果：清空effects(净化) '''
            for obj in explorer.effects:
                obj.use(explorer, _map, mode='recover')
            explorer.effects.clear()
        elif self.name == 'crayon':
            '''  蜡笔产生直接永久效果：在地图上留个圆圈标记 '''
            x, y = explorer.x, explorer.y
            r = int(y/_map.width)
            c = int(x/_map.width)
            w = int(_map.width*0.3)
            _map.marks[r][c].append(Mark('circle', [x,y], [w, w]))
        elif self.name == 'cat':
            '''  猫咪产生直接永久效果：在地图上留个到最近有效宝石或目的地的脚印（对方不可见） '''
            pass
        elif self.name == 'dog':
            '''  小狗产生直接永久效果：在地图上留个到最近有效宝石或目的地的脚印（对方也可见） '''
            pass
        # 限时BUFF类。
        elif self.name == 'snowflake':
            '''  雪花产生持续限时效果：减少移速到接近为0 '''
            if mode == 'apply':
                self.t = 4.5
                self.effect_name = 'effectFrozen'
                explorer.update_effects(copy.deepcopy(self), mode='add')
                Object.__func_change_v(explorer, 0.2)
            elif mode == 'recover':
                Object.__func_change_v(explorer, 1)
        elif self.name == 'mushroom':
            '''  蘑菇产生持续限时效果：随机移动，稍微减速。 '''
            ''' 很难，暂时用长时间的减速和变大代替。 '''
            if mode == 'apply':
                self.t = 6.0
                self.effect_name = 'effectPoisoned'
                explorer.update_effects(copy.deepcopy(self), mode='add')
                Object.__func_change_v(explorer, 0.3)
                Object.__func_change_size(explorer, _map, 1.5)
            elif mode == 'recover':
                Object.__func_change_v(explorer, 1)
                Object.__func_change_size(explorer, _map, 1)
        elif self.name == 'apple':
            ''' 苹果产生持续限时效果：增加移速 '''
            if mode == 'apply':
                self.t = 6.0
                self.effect_name = 'effectFaster'
                explorer.update_effects(copy.deepcopy(self), mode='add')
                Object.__func_change_v(explorer, 1.45)
            elif mode == 'recover':
                Object.__func_change_v(explorer, 1)
        elif self.name == 'lemon':
            ''' 柠檬产生持续限时效果：减少视野范围 '''
            if mode == 'apply':
                self.t = 6.0
                self.effect_name = 'effectBlinded'
                explorer.update_effects(copy.deepcopy(self), mode='add')
                Object.__func_change_fov(explorer, 0.25)
            elif mode == 'recover':
                Object.__func_change_fov(explorer, 1)
        elif self.name == 'watermelon':
            '''  西瓜产生持续限时效果：缩小体型 '''
            if mode == 'apply':
                self.t = 6.0
                self.effect_name = 'effectSmaller'
                explorer.update_effects(copy.deepcopy(self), mode='add')
                Object.__func_change_size(explorer, _map, 0.5)
            elif mode == 'recover':
                Object.__func_change_size(explorer, _map, 1)
        elif self.name == 'spice':
            ''' 辣椒产生持续限时效果：不能使用物品。（沉默） '''
            pass
        # 物品产生磨损。
        self.life_span -= self.depreciation

    # 功效函数
    @staticmethod
    def __func_change_size(explorer, _map, ratio):
        """ 改变体型(注意卡墙BUG) """
        # 原尺寸。
        w0, h0 = explorer.size
        # 新尺寸。
        explorer.width = int(explorer.SIZE_MAX[0] * ratio)
        explorer.height = int(explorer.SIZE_MAX[1] * ratio)
        explorer.size = [explorer.width, explorer.height]
        w, h = explorer.size
        # 如果是缩小，就直接返回。否则即使一起算，后面也会多出很多判断条件。
        if w0 >= w and h0 >= h:
            return
        # 原中心位置。
        x0, y0 = explorer.x, explorer.y
        dw, dh = w-w0, h-h0
        # 为了防止卡墙，可能需要重新计算形心。直接暴力去检验可能的几个适配方案即可。（枚举左上角偏移量）
        top_lefts = [[-w / 2, -h / 2],  # 均匀膨胀
                     [-w/2, h0/2-h], [-w/2, -h0/2], [-w0/2, -h/2], [w0/2-w, -h/2],  # 朝一个水平或竖直方向膨胀
                     [w0/2-w, h0/2-h], [w0/2-w, -h0/2], [-w0/2,h0/2-h], [-w0/2,-h0/2]]    # 朝对角方向膨胀
        for i, tl in enumerate(top_lefts):
            rect = [x0 + tl[0], y0 + tl[1], w, h]
            if _map.valid_area('rect', rect):
                # 最终位置的形心。
                explorer.x = rect[0] + w/2
                explorer.y = rect[1] + h/2
                explorer.pos = [explorer.x, explorer.y]
                return

    @staticmethod
    def __func_change_v(explorer, ratio):
        """ 改变移速 """
        explorer.v[0] = int(explorer.V_MAX[0] * ratio)
        explorer.v[1] = int(explorer.V_MAX[1] * ratio)

    @staticmethod
    def __func_change_fov(explorer, ratio):
        """改变视野范围 """
        explorer.fov = int(explorer.FOV_MAX * ratio)


class Mark:
    def __init__(self, name, pos, size):
        # 类型/名称：rect, circle, footprint(暂略).
        self.name = name
        # 所在的位置和大小
        self.x, self.y = int(pos[0]), int(pos[1])
        self.size = size
        # 虽然在地图上，但是mark可能有主人，仅对主人可见。-1表示所有人可见。
        self.visible_id = -1


class Action:
    """
    自定义的动作类。可以传输，只有最关键的游戏改变的动作。
    格式：动作类型，施加者，承受者，事件的值，其他参数。
    包括：
        开始更改方向  A对B
        放弃更改方向  A对B
        使用物品       A对B

    """
    ''' 动作类型 '''
    GAME_QUIT = 0   # 退出游戏
    MOVE_TURN = 1    # 转向
    MOVE_UNTURN = 2  # 停止转向（键盘松开）
    OBJ_USE = 3      # 物品使用
    OBJ_PICK = 4    # 物品拾取
    OBJ_PLACE = 5     # 把物品放置在某处
    CHAT_SEND = 6    # 发送信息

    def __init__(self, _type, _value, _applier, _target,  *args):
        self.type = _type       # 动作
        self.value = _value     # 动作的值
        self.applier = _applier  # 施加者（必须为玩家id）
        self.target = _target   # 承受者（必须为玩家id）
        self.args = args        # 可能的补充信息。

    def to_string(self):
        """ 将动作对象的主要信息转化成单个字符串，只是用于查看。 """
        return str(self.type)+':'+str(self.applier)+'-->'+str(self.target)


class Game:
    def __init__(self, n_players=1):
        """
        游戏有自己的视野边框，与Interface中的显示框大小无关。
        游戏有自己的坐标系。坐标以self.map的范围为准，map左上角为(0,0).
        game_status: (只会用于game.py, 网络服务器或interface都只是媒介。)
            'map': map对象；
            'explorers': explorers对象的列表；
            'objects': objects对象的列表；
            'events': 游戏事件的列表；
        actions = pygame.events 因为既然已经用了pygame,就没必要自己编写actions.
        """
        self.mode = 'RUNNING'
        self.winner = -1
        # 互斥锁（为了实现线程安全。放在最前，因为后续初始化过程会用到。）
        self.lock = threading.Lock()
        # 离散地图
        self.map = None
        self.init_map(rows_road=10, cols_road=8, width=100, density=0.90)
        # 根据地图的块宽度确定游戏的显示区域大小, 即不论屏幕大小，在屏幕里应该显示固定的多少视野。
        # 后续在screen中绘制时，会将显示区域拉伸填满整个screen，而不是不拉伸留黑。
        self.map_rows_per_height = 3  # 竖向在显示区域的地图块数量。
        self.height = self.map.width * self.map_rows_per_height
        self.width_height_ratio = 16 / 9
        self.width = int(self.height * self.width_height_ratio)
        self.size = [self.width, self.height]
        # 探险家对象列表（每个探险家都生成在相同的位置）
        self.n_players = n_players  # 必有参数。服务器会调用。默认为单人游戏。
        self.explorers = []
        self.init_explores(mode='fixed', size=[50, 50], r_road=1, c_road=1)
        # 在已有地图上生成物体对象，且与探险家不重合.
        self.init_objects()
        # 当前帧的动作列表。（是客户端的核心，非常重要！！！，每次绘制后会被刷新。）
        self.actions = []
        # 本地按键情况（用于和服务器发来的玩家方向进行校对）, [left, right, up, down]。
        self.dir_keys = [0, 0, 0, 0]
        # 即时事件列表（游戏发生的离散事件,Action类型加一个t，update_by_dt后每个减少dt.）
        self.events = []
        # 图片库、音轨库、字体库。为了客户端或单机下的渲染。
        self.path = 'resources/'
        self.materials = {
            'images': ['background', 'cursor', 'profile', 'victory', 'defeat'],
            'audios': ['envBirds', 'envCrickets',
                       'walk','pickCrystal','pickOthers','use',
                       'effectFrozen', 'effectPoisoned'],
            'fonts': ['times', 'simhei']
        }
        # 适配screen的方法。stretch 拉伸填满， letterbox 宽屏/留黑/比例不变。
        self.adjust_screen_style = 'stretch'
        # 音频通道列表。用于客户端播放音乐时候的控制。
        self.channels = dict()

    def __call__(self, func, **kwargs):
        """ 重写魔法函数call(),方便在interface中对所有元素（地图、玩家等）同时调用某函数。"""
        func(self, **kwargs)
        func(self.map, **kwargs)
        for explorer in self.explorers:
            func(explorer, **kwargs)

    def reset(self, n_players=1):
        self.__init__(n_players)

    def init_map(self, rows_road, cols_road, width, density=0.97):
        """ 生成地图 """
        with self.lock:
            self.map = Map(rows_road, cols_road, width, density)

    def init_explores(self, mode, size, **kwargs):
        """
        生成所有的探险家
        可选模式：
            random: 将所有探险家都随机分配到某个地图块中央。
            fixed: [r_road, c_road]
        """
        with self.lock:
            for _ in range(self.n_players):
                if mode == 'fixed':
                    r_road, c_road = kwargs['r_road'], kwargs['c_road']
                    x = (c_road*2+1)*self.map.width + self.map.width//2
                    y = (r_road*2+1)*self.map.width + self.map.width//2
                    self.explorers.append(Explorer([x, y], size))

    def init_objects(self):
        """ 生成所有的互动物体 """
        with self.lock:
            # 物品信息。名字：[[width, height], 个数]。从大到小排列，防止draw时覆盖。
            # objects_list 最好由参数提供，这样可以从设置中读取。这里暂不写。
            objects_list = {
                'watermelon': [[50, 40], 4],
                'lemon': [[20,20],2],
                'apple': [[20,20],4],
                #
                'snowflake': [[20,20],4],
                'coffee': [[20,20],5],
                'mushroom': [[20,20],3],
                # 带折损的物品。
                'crayon': [[30, 30], 4, 15],

                #
                'crystalScarlet': [[30,30], 3],
                'crystalGreen': [[20, 20], 3],
                'crystalBlue': [[20, 20], 3],
                # 终点
                'destination': [[50, 50], 2]
            }
            for name,info in objects_list.items():
                size,num=info[0], info[1]
                # 将素材库加入到map的素材库中
                self.map.materials['images'].append(name)
                # 随机生成对应数量的物体，添加到map中
                for inum in range(num):
                    placed = False
                    while not placed:
                        r = random.randint(1, self.map.rows - 2)
                        c = random.randint(1, self.map.cols - 2)
                        if self.map.maze[r][c] > 0:
                            # 计算探险家的初始位置，确保物体生成位置与之不重合。
                            overlap = False
                            for explorer in self.explorers:
                                r_e = int(explorer.y / self.map.width)
                                c_e = int(explorer.x / self.map.width)
                                if (r_e, c_e) == (r, c):
                                    overlap = False
                                    break
                            if not overlap:
                                # 在选定的地图块上，再随机选择坐标（中心点）。
                                ex = random.randint(size[0] // 2, self.map.width - size[0] // 2)
                                ey = random.randint(size[1] // 2, self.map.width - size[1] // 2)
                                x = ex + c * self.map.width
                                y = ey + r * self.map.width
                                # 是否为非一次性物品？
                                depreciation = 100 if len(objects_list[name])<3 else objects_list[name][2]
                                # 创建并添加
                                self.map.objects[r][c].append(Object(name, [x, y], size, depreciation))
                                placed = True

    def selfmade_images(self):
        """ 有一些图片不是提前画好放在resources中的，而是临时预先生成的。 """
        images = dict()
        pos_area_ctr = pos_area_ctr = [self.size[0] // 2, self.size[1] // 2]

        # 视野滤镜  (在一张具有alpha通道的表面上画一系列渐变的透明的圆就行了）
        def fov_filter(fov):
            # 分成两部分，前面渐变快点，后面渐变慢点。
            fov_min = int(fov*0.01)
            fov_mid = int(fov*0.5)
            fov_max = int(fov*2.5)
            opacity_mid = 150
            surf_mask = pygame.Surface(self.size, pygame.SRCALPHA)
            # 设置不透明部分的颜色
            surf_mask.fill((10, 0, 20))
            # 在表面上绘制一圈圈透明圆形
            # 越内层，不透明度越低，最内层为0。最外层的不透明度为255.
            for r in range(fov_max, fov_mid, -2):
                opacity_d = 255 - opacity_mid
                opacity = opacity_mid + int(opacity_d*(r - fov_mid)/(fov_max - fov_mid))
                pygame.draw.circle(surf_mask, (0, 0, 0, opacity), pos_area_ctr, r)
            for r in range(fov_mid, fov_min, -2):
                opacity = 0 + int(opacity_mid*(r - fov_min)/(fov_mid - fov_min))
                pygame.draw.circle(surf_mask, (0, 0, 0, opacity), pos_area_ctr, r)
            return surf_mask
        images['fovNormal'] = [fov_filter(self.explorers[0].fov)]
        images['fovShort'] = [fov_filter(self.explorers[0].fov*0.5)]
        images['fovLong'] = [fov_filter(self.explorers[0].fov*1.5)]

        # 被中毒效果滤镜（可旋转。）
        def effect_poisoned():
            for fname in os.listdir(self.path + 'images'):
                if fname.startswith('_effectPoisoned'):
                    surf = pygame.image.load(self.path + 'images/' + fname)
                    surf = pygame.transform.scale(surf, self.size).convert_alpha().convert()
                    surf.set_alpha(20)
                    return surf
        images['effectPoisoned'] = [effect_poisoned()]

        # 被冰冻效果滤镜（多帧）
        def effect_frozen():
            for fname in os.listdir(self.path + 'images'):
                if fname.startswith('_effectFrozen'):
                    surf = pygame.image.load(self.path + 'images/' + fname)
                    surf = pygame.transform.scale(surf, self.size).convert_alpha().convert()
                    surf.set_alpha(80)
                    return surf
        images['effectFrozen'] = [effect_frozen()]

        # 被致盲效果滤镜
        images['effectBlinded'] = [fov_filter(self.explorers[0].fov * 0.3)]
        return images

    def update_by_actions(self, i_explorer, actions):
        """ 根据传递来的actions更新游戏。 actions[i]是自定义的Action对象。 """
        ''' 
        改进：任何动作都是尝试性的！服务器必须先进行合法性检验然后才进行实质性更改。
        '''
        with self.lock:
            if self.mode == 'GAMEOVER':
                return
            for action in actions:
                # 游戏退出。(暂略）
                #
                applier = self.explorers[action.applier]
                target = self.explorers[action.target]
                # 尝试动作：人物转向。
                if action.type == Action.MOVE_TURN:
                    target.update_direction(action.value, 1)
                elif action.type == Action.MOVE_UNTURN:
                    target.update_direction(action.value, 0)
                # 尝试动作：物品拾取。value=obj, args=[r,c].
                elif action.type == Action.OBJ_PICK:

                    obj = action.value
                    r, c = action.args
                    # 对于服务器，要拾取的物品是否还在地上？
                    if obj not in self.map.objects[r][c]:
                        return
                    # 对于服务器，要拾取的物品是否在玩家的拾取范围内？
                    x = target.x
                    y = target.y
                    act_range = target.act_scale * min(target.size)/2
                    if (x-obj.x)**2+(y-obj.y)**2 > act_range**2:
                        return
                    # 如果该物体是终点标记，且玩家对应的水晶足够，则赢取游戏。
                    if obj.name.startswith('destination'):
                        if len(applier.crystals_found) >= 3:
                            self.mode = 'GAMEOVER'
                            self.winner = action.applier
                            return
                    # 如果该物体是水晶，且玩家对应的水晶不够，就拾取并让该水晶数变为1，否则放弃。
                    elif obj.name.startswith('crystal'):
                        if obj.name not in applier.crystals_found:
                            applier.crystals_found[obj.name] = 1
                            self.map.objects[r][c].remove(obj)
                            # 构成了游戏事件通告。
                            self.events.append([action, 1.5])
                    # 如果该物体是其他，且玩家的背包未满，就拾取，否则放弃。
                    else:
                        if applier.update_bag(obj, 'add'):
                            self.map.objects[r][c].remove(obj)
                # 尝试动作：物品放置。
                elif action.type == Action.OBJ_PLACE:
                    # 对于服务器，要放置的物品是否还在背包？
                    pass
                # 尝试动作：物品使用。
                elif action.type == Action.OBJ_USE:
                    obj = applier.bag[action.value]
                    # 对于服务器，所要使用的物品是否还在背包？
                    if not obj:
                        return
                    # 使用。然后计算物品的剩余寿命。
                    obj.use(target, self.map)
                    if obj.life_span <= 0:
                        self.explorers[action.applier].update_bag(action.value, mode='remove')
                    # 如果是玩家间互相使用，则构成一个游戏事件通告,把物品位置换成物品，然后存储。
                    if action.applier != action.target:
                        action.value = obj
                        # 将[动作，持续时间]加入游戏事件通告列表。
                        self.events.append([action, 1.5])

    def update_by_dt(self, dt):
        """ 根据时间间隔dt更新游戏。检测碰撞和互动，减去dt的时效。 """
        with self.lock:
            if self.mode == 'GAMEOVER':
                return
            # explorer移动。
            for i_explorer, explorer in enumerate(self.explorers):
                w, h = explorer.width, explorer.height
                # 计算可能的下一个位置。（尝试移动）
                xn, yn = explorer.next_pos(dt)
                # 如果位置不合法就缩小一下dt,依次尝试dt/2, dt/4, dt/8, ...。
                if not self.map.valid_area('rect', [xn - w // 2, yn - h // 2, w, h]):
                    xn, yn = explorer.next_pos(dt/2)
                    if not self.map.valid_area('rect', [xn - w // 2, yn - h // 2, w, h]):
                        xn, yn = explorer.next_pos(dt/4)
                if self.map.valid_area('rect', [xn-w//2, yn-h//2, w, h]):
                    explorer.x = xn
                    explorer.y = yn

            # 对于任何有时效的东西，都减去dt的时效。
            # 身上的effects，统一更新。
            explorer.update_effects(dt, self.map, mode='update')
            # 游戏事件 -dt
            i_event = 0
            while i_event<len(self.events):
                self.events[i_event][1] -= dt
                if self.events[i_event][1] < 0:
                    self.events.pop(i_event)
                else:
                    i_event += 1

    def get_status(self):
        """ 获取当前游戏中各元素的坐标和状态，并读取并清空在上个周期内发生的所有离散事件。 """
        ''' 主要是因为self.lock无法用pickle，同时get_status也是线程安全的。 '''
        with self.lock:
            status = dict()
            status['mode'] = self.mode
            status['winner'] = self.winner
            status['map'] = copy.deepcopy(self.map)
            status['explorers'] = copy.deepcopy(self.explorers)
            status['events'] = copy.deepcopy(self.events)
            return status

    def draw_and_act(self, screen, status, resources, frame, main_player_id = 0):
        """
        draw:
        以 main_player_id所对应的玩家为中心，绘制status.
        应该只有绘制game_status的函数，而没有绘制game的函数。在线的和单机的共用。
        所以，注意函数中所以涉及self的都应该是常数，变量在status中。
        将游戏显示区域area绘制在interface的screen上时，有三种方法：
            （1） area固定，即直接贴在screen上。这种情况会导致screen越大则留黑越大。
            （2） area拉伸填满screen. 这种情况会导致screen长宽比变化时游戏画面也被拉成歪的。
            （3） area等比例拉伸，填满screen。这种情况会导致screen会有一侧的留黑。
        选择第（2）种。且采用最普遍的16:9比例area, 能适应大部分screen和全屏screen.
        这在interface中的resources里实现图片的提前全部拉伸。(想了下，发现应该临时拉伸。)
        先创建一个临时表面，全部画完后再适配screen,这样能省去很多步骤。

        act:
        绘制的过程中，捕捉鼠标和键盘造成的有效action,刷新self.actions.

        soundtrack:
        游戏内部的事件音效等。
        """
        # 随机切换背景音乐。
        def bgm():
            # 如果env音轨不存在或无播放，则随机选择一个bgm进行播放。
            if 'env' not in self.channels or (not self.channels['env'].get_busy()):
                # [文件名，音量]
                env_list = [['envBirds', 0.2], ['envCrickets',0.9]]
                # 随机选择一个音乐。
                ith = random.randint(0, 1)
                my_music = resources.audios[env_list[ith][0]]
                my_music.set_volume(env_list[ith][1])
                length = my_music.get_length()
                channel = my_music.play(maxtime=int(min(length, 90)*1000))
                self.channels['env'] = channel
        bgm()
        # 当前玩家
        my_id = main_player_id
        me = status['explorers'][my_id]
        # 清空动作列表。
        self.actions.clear()
        events = pygame.event.get()
        # 鼠标的点击状态(左键1中键2右键3)先记录下来，后面配合画面会产生action.
        mouse_clicked = [0, 0, 0] # 1按下，2松开。
        # 捕捉键盘action。
        # 方向键。
        dir_keys = {pygame.K_LEFT: 0, pygame.K_a: 0,
                      pygame.K_RIGHT: 1, pygame.K_d: 1,
                      pygame.K_UP: 2, pygame.K_w: 2,
                      pygame.K_DOWN: 3, pygame.K_s: 3
                      }
        # 记录空格键等是否被点击。用于和鼠标坐标配合来生成动作。
        keys_others = {pygame.K_SPACE: False, pygame.K_1: False}
        for event in events:
            if event.type == pygame.QUIT:
                self.actions.append(Action(Action.GAME_QUIT, 0, my_id, my_id))
            if event.type == pygame.KEYDOWN:
                if event.key in dir_keys:
                    self.dir_keys[dir_keys[event.key]] = 1
                    self.actions.append(Action(Action.MOVE_TURN,
                                               dir_keys[event.key], my_id, my_id))
            if event.type == pygame.KEYUP:
                if event.key == pygame.K_ESCAPE:
                    self.actions.append(Action(Action.GAME_QUIT, 0, my_id, my_id))
                if event.key in dir_keys:
                    self.dir_keys[dir_keys[event.key]] = 0
                    self.actions.append(Action(Action.MOVE_UNTURN,
                                               dir_keys[event.key], my_id, my_id))
                if event.key in keys_others:
                    keys_others[event.key] = True
            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_clicked[event.button-1] = 1
            if event.type == pygame.MOUSEBUTTONUP:
                mouse_clicked[event.button-1] = 2
        # 校正本地的按键情况和服务器发来的主玩家的方向是否匹配，如果不匹配则需要重发转向动作！
        if tuple(me.direction) != tuple(self.dir_keys):
            for i, _direction in enumerate(self.dir_keys):
                act_type = Action.MOVE_TURN if _direction == 1 else Action.MOVE_UNTURN
                self.actions.append(Action(act_type, i, my_id, my_id))

        # 创建临时surface.
        surf = pygame.Surface(self.size)
        # 读取当前主视角玩家的中心坐标, 标记为视野中心。计算平移量。
        pos_me = [int(me.x), int(me.y)]
        pos_area_ctr = [self.size[0]//2, self.size[1]//2]
        pos_offset = [pos_area_ctr[0]-pos_me[0], pos_area_ctr[1]-pos_me[1]]
        # 读取当前鼠标的位置。只是起到和界面的交互作用。需要从screen坐标转换成游戏的坐标。
        pos_cursor_screen = pygame.mouse.get_pos()
        pos_cursor = [pos_cursor_screen[0]*self.size[0]/screen.get_width(),
                      pos_cursor_screen[1]*self.size[1]/screen.get_height()]
        '''
        快捷函数：先不screen适配, 将某关键字key所对应的图片集的第frame张图(以step为间隔)
                    进行offset后贴在某处,可以选择固定为第fixed张。
        '''
        def stick(key, size, pos, step=1, fixed=-1, offset=True):
            x = pos[0] + pos_offset[0]
            y = pos[1] + pos_offset[1]
            length = len(resources.images[key])
            # 每step帧才变化。
            ith = (frame // step) % length if fixed < 0 else fixed
            img_surf = pygame.transform.scale(resources.images[key][ith],
                                              [size[0], size[1]])
            surf.blit(img_surf, [x, y])

        # 绘制静态背景图。（最下层）
        def draw_background():
            surf.blit(pygame.transform.scale(resources.images['background'][0],
                                             self.size), [0,0])
        draw_background()

        # 绘制i_explorer视野内的地图块、标记和物体: 先绘制地面，再绘制墙体。
        def draw_map():
            # 计算pos_center在哪一行哪一列
            c_ctr = pos_me[0] // status['map'].width
            r_ctr = pos_me[1] // status['map'].width
            # 绘制以pos_center为中心的地图块。
            rows_half = self.map_rows_per_height//2 + 1
            cols_half = int(self.map_rows_per_height*self.width_height_ratio/2) + 1
            # 绘制路面。
            for r in range(max(0, r_ctr-rows_half),
                           min(self.map.rows, r_ctr+rows_half+1)):
                for c in range(max(0, c_ctr-cols_half),
                               min(self.map.cols, c_ctr+cols_half+1)):
                    x = c*status['map'].width
                    y = r*status['map'].width
                    img_expand = 1.07
                    w = int(self.map.width*img_expand)
                    h = int(self.map.width*img_expand)
                    if status['map'].maze[r][c] == 1:
                        stick('road', [w,h], [x, y], 1)
            # 绘制路面上的标记。（需要等路面全部绘制完毕才能绘制）
            for r in range(max(0, r_ctr-rows_half),
                           min(self.map.rows, r_ctr+rows_half+1)):
                for c in range(max(0, c_ctr-cols_half),
                               min(self.map.cols, c_ctr+cols_half+1)):
                    for mark in status['map'].marks[r][c]:
                        # 仅绘制主玩家可见的标记。
                        if mark.visible_id == -1 or mark.visible_id == my_id:
                            x = int(mark.x + pos_offset[0])
                            y = int(mark.y + pos_offset[1])
                            pygame.draw.circle(surf, [10,10,100],[x, y],
                                               mark.size[0]//2, 1)
            # 绘制路面上的物体。（需要等路面和标记全部绘制完毕才能绘制）
            for r in range(max(0, r_ctr-rows_half),
                           min(self.map.rows, r_ctr+rows_half+1)):
                for c in range(max(0, c_ctr-cols_half),
                               min(self.map.cols, c_ctr+cols_half+1)):
                    for obj in status['map'].objects[r][c]:
                        x = int(obj.x - obj.size[0]/2)
                        y = int(obj.y - obj.size[1]/2)
                        stick(obj.name, obj.size, [x, y], 4)
            # 绘制墙体。
            for r in range(max(0, r_ctr - rows_half),
                           min(self.map.rows, r_ctr + rows_half + 1)):
                for c in range(max(0, c_ctr - cols_half),
                               min(self.map.cols, c_ctr + cols_half + 1)):
                    # 绘制墙体单元（墙体增大的时候是各向同比例的）
                    img_expand = 1.12
                    dw = int(self.map.width * (img_expand-1))
                    dh = int(self.map.width * (img_expand - 1))
                    w = self.map.width + dw
                    h = self.map.width + dh
                    x = c * status['map'].width - dw//2
                    y = r * status['map'].width - dh//2
                    if status['map'].maze[r][c] == 0:
                        stick('wall', [w, h], [x, y], 1)
                    # 绘制墙体上的物体
                    for obj in status['map'].objects[r][c]:
                        x = int(obj.x - obj.size[0] / 2)
                        y = int(obj.y - obj.size[1] / 2)
                        stick(obj.name, obj.size, [x, y], 4)
        draw_map()

        # 绘制所有玩家（注意：玩家坐标和玩家图片左上角坐标的关系）。
        def draw_explorers():
            for i_explorer, explorer in enumerate(status['explorers']):
                x = int(explorer.x - explorer.size[0]/2)
                y = int(explorer.y - explorer.size[1]/2)
                # 判断是否站立，若站立，图像没有动画。
                stand = 0
                if explorer.direction[0] != explorer.direction[1] or \
                        (explorer.direction[2] != explorer.direction[3]):
                    stand = -1
                # 人物动画的帧率（与速度有关，满速时每1帧就换一次。）
                step = max(1, int(explorer.V_MAX[0]/explorer.v[0]))
                # 这里注意，只能绘制一张图。
                dir_names = ['explorerLeft','explorerRight','explorerUp','explorerDown']
                # 绘制。
                stick(dir_names[explorer.facial_orientation], explorer.size, [x, y], step, stand)
                '''
                脚步声：如果人物在画面里，且direction不为0，则持续播放，否则停止。
                    离中心越近声音越大。所以统一为：在一个区域内声音从0到1.
                    将来进阶：控制左右声道，产生立体效果。
                '''
                playing = ('walk' in self.channels and self.channels['walk'].get_busy())
                # 在移动。判断是否有音轨且在播放。
                if explorer.direction[0] != explorer.direction[1] or\
                    (explorer.direction[2] != explorer.direction[3]):
                    if not playing:
                        r2 = (explorer.x - pos_area_ctr[0])**2 \
                             + (explorer.y - pos_area_ctr[1])**2
                        # 能听到声音的极限距离。
                        r2max = (max(self.size[0],self.size[1]))**2
                        # 计算音量。
                        volume = (r2max - r2)/r2max
                        # 播放。
                        if volume > 0:
                            resources.audios['walk'].set_volume(volume)
                            self.channels['walk'] = resources.audios['walk'].play()
                        else:
                            resources.audios['walk'].stop()
                # 不在移动。判断是否有音轨，如果有就关掉。
                else:
                    if playing:
                        resources.audios['walk'].stop()
        draw_explorers()

        # 对于主玩家，检查是否在生成一些拾取等动作。
        def act_explorer():
            # 拾取动作。
            if keys_others[pygame.K_SPACE]:
                # 计算pos_center在哪一行哪一列
                c_ctr = pos_me[0] // status['map'].width
                r_ctr = pos_me[1] // status['map'].width
                # 计算以pos_center为中心的上下左右最多9个地图块。
                for r in range(max(0, r_ctr-1), min(r_ctr+2, status['map'].rows)):
                    for c in range(max(0, c_ctr-1), min(c_ctr+2, status['map'].cols)):
                        for obj in status['map'].objects[r][c]:
                            if (me.x-obj.x)**2+(me.y-obj.y)**2 <= (me.act_scale * min(me.size)/2)**2:
                                self.actions.append(Action(Action.OBJ_PICK, obj, my_id, my_id, r, c))
                                # 播放拾取音效。（即使拾取失败, 以本地判断为准。）
                                resources.audios['pickOthers'].set_volume(0.15)
                                resources.audios['pickOthers'].play()
        act_explorer()

        # 绘制能挡住玩家的地图元素。

        # 绘制主玩家视野filter.
        def draw_fov():
            if me.fov < me.FOV_MAX:
                stick('fovShort', self.size, [-pos_offset[0], -pos_offset[1]])
            else:
                stick('fovNormal', self.size, [-pos_offset[0], -pos_offset[1]])
        draw_fov()

        def draw_effects():
            effects_considered = ['effectFrozen', 'effectPoisoned']
            effects_working = [_.effect_name for _ in me.effects]
            for obj in me.effects:
                effect_name = obj.effect_name
                if effect_name in effects_considered:
                    surf.blit(pygame.transform.scale(resources.images[effect_name][0],
                                                     self.size), [0, 0])
                    # 打开音效。
                    playing = (effect_name in self.channels
                               and self.channels[effect_name].get_busy())
                    if not playing:
                        self.channels[effect_name] = resources.audios[effect_name].play()
            # 正在施加的effect，需要有音效。
            # self.channels中如果有正在播的effectXXX而该效果已经不存在，则停止播放。
            for ch_name, channel in self.channels.items():
                if ch_name.startswith('effect'):
                    if ch_name not in effects_working and channel.get_busy():
                        resources.audios[ch_name].stop()
        draw_effects()

        # 绘制背包，同时响应可能的点击。
        def draw_bag(position='bottom'):
            # 先确定每个方框的大小。
            dw, dh = 20, 20
            n = len(me.bag)
            # 绘制在下方中央，铺开。
            if position == 'bottom':
                # 方框左上角的纵坐标
                y0 = self.size[1] - dh * 2
                # 方框之间的间距
                gap_x = int(dw * 0.6)
                # 计算正中央时的最左端坐标
                x0 = int((self.size[0] - dw * n - gap_x * (n - 1)) / 2)
                for i, obj in enumerate(me.bag):
                    x = x0 + (dw+gap_x)*i
                    y = y0
                    # 物品
                    if obj:
                        surf.blit(pygame.transform.scale(resources.images[obj.name][0],
                                                        [dw, dh]), [x, y])
                    # 绘制边框（如果鼠标在方框内，就变色加粗，且显示物品信息。)
                    if x<=pos_cursor[0]<=x+dw and y<=pos_cursor[1]<=y+dh:
                        pygame.draw.rect(surf, [0, 200, 0], [x-1, y-1, dw, dh], 2)
                        if obj:
                            # 绘制信息的边框,左上角(x_text, y_text),总宽度w_text.
                            h_text = dh*1.0
                            y_text = y - dh*1.2
                            w_text = 0.4*self.width
                            x_text = max(5, x-w_text/2)
                            pygame.draw.rect(surf, [100, 100, 100], [x_text, y_text, w_text, h_text], 1)
                            # 绘制文本
                            msg = Object.INFO[obj.name][1]
                            th = int(dh * 0.45)
                            font = pygame.font.Font(resources.fonts['simhei'], th)
                            text_surface = font.render(msg, True, (255, 200, 255))
                            surf.blit(text_surface, [x_text+th*0.2, y_text+th*0.2])
                            # 如果同时还有右键松开，且obj不为空，就发送act.
                            # 鼠标左键，给敌方(-1下标)使用。
                            if mouse_clicked[0] == 2:
                                self.actions.append(Action(Action.OBJ_USE, i, my_id, -1))
                            # 鼠标右键，给自己使用。
                            if mouse_clicked[2] == 2:
                                self.actions.append(Action(Action.OBJ_USE, i, my_id, my_id))
                    else:
                        pygame.draw.rect(surf, [0, 200, 200], [x, y, dw, dh], 1)
        draw_bag()

        # 绘制所有玩家的头像、水晶进度和网速（绘制在左上侧）：
        def draw_profile_status():
            # 先确定每个方框的大小。
            dw, dh = 35, 35
            # 头像方框左上角的公共横坐标
            x0 = dw * 0.4
            # 头像方块左上角的初始纵坐标
            y0 = dh * 0.5
            # 方框上下的间距
            gap_y = int(dh * 0.6)
            for i, e in enumerate(status['explorers']):
                x = x0
                y = y0 + (dh + gap_y)*i
                # 头像和边框
                surf.blit(pygame.transform.scale(resources.images['profile'][0],
                                                 [dw, dh]), [x, y])
                pygame.draw.rect(surf, [100, 100, 0], [x , y , dw, dh], 1)
                # 如果这是你自己，那么用绿框标出。
                if i == main_player_id:
                    pygame.draw.rect(surf, [50, 100, 50], [x-1, y-1, dw, dh], 3)

                # 网速（略）
                # 水晶拾取状态
                gap_x = int(dw*0.2)
                xx0 = x+dw+gap_x
                yy0 = y+dh*0.3
                dww = int(dw*0.5)
                dhh = int(dh*0.5)
                for j, crystal_name in enumerate(e.crystals_found.keys()):
                    xx = xx0+j*(dww+dww*0.3)
                    yy = yy0
                    surf.blit(pygame.transform.scale(resources.images[crystal_name][0],
                                                     [dww, dhh]), [xx, yy])
            return
        draw_profile_status()

        # 绘制游戏事件。(绘制在中央上侧)
        def draw_events():
            w = int(0.5 * self.size[0])
            h = int(0.07 * self.size[1])
            y0 = 0.1 * self.size[1]
            x0 = (self.size[0] - w) / 2
            for i, _event in enumerate(status['events']):
                action, time_remain = _event
                x = x0
                y = y0 + i*h
                # 通告的文本
                msg = ''
                # 边框的颜色
                color_rect = [20,200,40]
                if action.type == Action.OBJ_USE:
                    if action.applier == my_id:
                        msg += '你给对方使用了'+Object.INFO[action.value.name][0]
                    else:
                        msg += '对方给你使用了'+Object.INFO[action.value.name][0]
                        color_rect = [200,0,0]
                elif action.type == Action.OBJ_PICK:
                    if action.applier == my_id:
                        msg += '你收集到了'+Object.INFO[action.value.name][0]
                    else:
                        msg += '对方收集到了'+Object.INFO[action.value.name][0]
                        color_rect = [200,0,0]
                # 绘制通告的边框
                pygame.draw.rect(surf, color_rect, [x, y, w, h], 1)
                # 绘制文本
                th = int(h*0.7)
                font = pygame.font.Font(resources.fonts['simhei'], th)
                text_surface = font.render(msg, True, (255, 200, 255))
                surf.blit(text_surface, [x+h, y + (h - th)/2])

        draw_events()

        # 绘制鼠标（最上层）

        # 如果游戏已结束，则绘制游戏结算画面。
        def draw_gameover():
            if status['mode'] == 'GAMEOVER':
                key = 'victory' if main_player_id == status['winner'] else 'defeat'
                img_surf = pygame.transform.scale(resources.images[key][0], self.size)
                surf.blit(img_surf, [0, 0])
        draw_gameover()

        # 与screen适配（最终）
        def adjust_screen():
            size_screen = [screen.get_width(), screen.get_height()]
            if self.adjust_screen_style == 'stretch':
                screen.blit(pygame.transform.scale(surf, size_screen), [0,0])
            elif self.adjust_screen_style == 'letterbox':
                if self.size[0]/self.size[1] < size_screen[0]/size_screen[1]:
                    # 屏幕长度不够。按长度拉伸游戏画面，屏幕上下留黑。
                    w = size_screen[0]
                    h = w*self.size[1]//self.size[0]
                    h_gap = size_screen[1] - h
                    screen.blit(pygame.transform.scale(surf, [w,h]), [0, h_gap//2])
                else:
                    # 屏幕宽度不够。按宽度拉伸游戏画面，屏幕左右留黑。
                    h = size_screen[1]
                    w = h * self.size[0] // self.size[1]
                    w_gap = size_screen[0] - w
                    screen.blit(pygame.transform.scale(surf, [w, h]), [w_gap // 2, 0])
        adjust_screen()
