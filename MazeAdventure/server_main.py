import network
import game

server_address = ('0.0.0.0', 17777)
my_game = game.Game(2)
server = network.NetworkServer(server_address, my_game)
server.run()







