import interface, network, game
import os

# SERVER_IP, SERVER_PORT = '192.168.7.65', 35777
SERVER_IP, SERVER_PORT = '121.36.213.171', 35777

''' 限制使用次数：N次 '''
n_limits = 15
pref = 'feaddfef3243545654653432435435hhfgh234676587454500054354'
suff = '089327489334324354354654723259809854375348972uirejfijfsjdfklsjdlkf43543234324354345454654576534534656'
n1=len(pref)
n2=len(suff)


def check_limits(admin=False):
    if not os.path.exists('client_limits.txt'):
        if not admin:
            return False
        else:
            f=open('client_limits.txt','w')
            f.write(pref+str(n_limits)+suff)
    f = open('client_limits.txt','r')
    s = f.readline()
    n=len(s)
    if s[:n1]!=pref or s[n-n2:n]!=suff:
        return False
    num = int(s[n1:n-n2])
    print('剩余次数：',num)
    f.close()
    if num <= 0:
        return False
    else:
        num -= 1
        f = open('client_limits.txt', 'w')
        f.write(pref + str(num) + suff)
        return True


def test_interface_client():
    if not check_limits(admin=True):
        return
    client = network.NetworkClient(SERVER_IP, SERVER_PORT)
    my_game = game.Game()
    intf = interface.Interface(my_game)
    intf.bind_network(client)
    intf.run()


if __name__ == '__main__':
    test_interface_client()







