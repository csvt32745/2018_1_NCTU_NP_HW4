import sys
import socket
import json
import os
#from stomp import *
import stomp
class Listener():
    def on_message(self, headers, msg):
        print(msg)

class UserInfo():
    def __init__(self, name, token):
        self.username = name
        self.token = token
        #self.user_sub = sub_id
        #sub_id = token
        self.group_sub = {}


class Client(object):
    def __init__(self, ip, port):
        try:
            socket.inet_aton(ip)
            if 0 < int(port) < 65535:
                self.ip = ip
                self.port = int(port)
            else:
                raise Exception('Port value should between 1~65535')
            
        except Exception as e:
            print(e, file=sys.stderr)
            sys.exit(1)

        self.cmd_user = ''
        self.users = {}
        self.amq = stomp.Connection([(self.ip, 61613)])
        self.amq.set_listener('', Listener())
        self.amq.connect()

    def run(self):
        while True:
            cmd = sys.stdin.readline()
            if cmd == 'exit' + os.linesep:
                return
            if cmd != os.linesep:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.connect((self.ip, self.port))
                        cmd = self.__attach_token(cmd)
                        s.send(cmd.encode())
                        resp = s.recv(4096).decode()
                        self.__show_result(json.loads(resp), cmd)
                except Exception as e:
                    print(e, file=sys.stderr)

    def __show_result(self, resp, cmd=None):
        if 'message' in resp:
            print(resp['message'])

        if 'invite' in resp:
            if len(resp['invite']) > 0:
                for l in resp['invite']:
                    print(l)
            else:
                print('No invitations')

        if 'friend' in resp:
            if len(resp['friend']) > 0:
                for l in resp['friend']:
                    print(l)
            else:
                print('No friends')

        if 'post' in resp:
            if len(resp['post']) > 0:
                for p in resp['post']:
                    print('{}: {}'.format(p['id'], p['message']))
            else:
                print('No posts')

        if 'group' in resp:
            if len(resp['group']) > 0:
                for g in resp['group'] :
                    print(g)
            else:
                print('No groups')

        if cmd:
            command = cmd.split()
            if resp['status'] == 0 :
                if  command[0] == 'login':
                    self.users[self.cmd_user] = UserInfo(self.cmd_user, resp['token'])
                    self.__amq_subscribe(self.cmd_user)

                elif command[0] == 'logout' or command[0] == 'delete':
                    self.__amq_user_unsub(self.users[self.cmd_user])
                    self.users.pop(self.cmd_user)
                
                if 'group_info' in resp:
                    for g in resp['group_info']:
                        self.users[self.cmd_user].group_sub[g['groupname']] = '/topic/' + g['channel']
                        self.__amq_subscribe('/topic/' + g['channel'])
                        

    def __attach_token(self, cmd=None):
        if cmd:
            command = cmd.split()
            if len(command) > 1:
                self.cmd_user = command[1]
                if command[0] != 'register' and command[0] != 'login':
                    if command[1] in self.users:
                        command[1] = self.users[command[1]].token
                    else:
                        command.pop(1)
            return ' '.join(command)
        else:
            return cmd

    def __amq_subscribe(self, channel):
        #self.amq.connect()
        self.amq.subscribe(channel, channel)
        #self.amq.disconnect()

    def __amq_user_unsub(self, userinfo):
        #self.amq.connect()
        self.amq.unsubscribe(userinfo.username)
        for ele in userinfo.group_sub.values():
            self.amq.unsubscribe(ele)
        #self.amq.disconnect()

def launch_client(ip, port):
    c = Client(ip, port)
    c.run()

if __name__ == '__main__':
    if len(sys.argv) == 3:
        launch_client(sys.argv[1], sys.argv[2])
    else:
        print('Usage: python3 {} IP PORT'.format(sys.argv[0]))
