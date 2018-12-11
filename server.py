import sys
import socket
import json
import hashlib
import random
import time
from peewee import *
import stomp

def print_func_name(func):
    def wrapper(*func_args, **func_argv):
        print('Start func: ', func.__name__)
        return func(*func_args, **func_argv)
    return wrapper

db = MySQLDatabase(
    'NP',
    user = 'Alan',
    passwd = '123456',
    host = '140.113.122.19',
    port = 3306
)

class BaseModel(Model):
    class Meta:
        database = db

class User(BaseModel):
    username = CharField(64, unique = True)
    token = CharField(64, null = True)
    # AMQ channel = token
    password = CharField(64)

class FriendPair(BaseModel):
    # friend_1 has smaller ID than friend_2
    friend_1 = ForeignKeyField(User, related_name = 'friends_1')
    friend_2 = ForeignKeyField(User, related_name = 'friends_2')

class FriendInvite(BaseModel):
    receiver = ForeignKeyField(User, related_name = 'recv_invites')
    sender = ForeignKeyField(User, related_name = 'send_invites')

class Post(BaseModel):
    user = ForeignKeyField(User, related_name = 'posts')
    text = TextField()

class Group(BaseModel):
    groupname = CharField(64, unique = True)
    channel = CharField(64)

class GroupMember(BaseModel):
    group = ForeignKeyField(Group, related_name = 'members')
    user = ForeignKeyField(User, related_name = 'group')

class Server:
    def __init__(self, _host, _port):
        self.host = _host
        self.port = _port
        self.cmd_str = ''
        self.cmd_frag = []
        self.cmd_switch = {
            'register': self.register,
            'login': self.login,
            'delete': self.delete,
            'logout': self.logout,
            'invite': self.invite,
            'list-invite':self.listInvt,
            'accept-invite':self.acptInvt,
            'list-friend':self.listFrnd,
            'post':self.post,
            'receive-post':self.recvPost,
            'send':self.sendMsg
        }
        db.connect()
        db.create_tables([User, FriendPair ,FriendInvite, Post, Group, GroupMember])

    def run(self):
        while True:
            self.passiveTCP()

    def passiveTCP(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.host, self.port))
            print('--------------------')
            print('Sever is ready for listening...')
            s.listen(1)
            client, addr = s.accept()
            with client:
                print(time.asctime(time.localtime()))
                print('Connect: ', addr)
                self.cmd_str = client.recv(1024).decode()
                print('Received: ', self.cmd_str)
                client.sendall(self.cmdProcess().encode('UTF-8'))
                s.close()
    
    #@staticmethod
    def createResp(self, status, message = '', 
    token = '', post = '', friend = '', invite = ''):
        resp = { 'status': status }
        if token:
            resp['token'] = token
        if message:
            resp['message'] = message
        if self.cmd_frag[0] == 'receive-post' and not status:
            resp['post'] = post
        if self.cmd_frag[0] == 'list-friend' and not status:
            resp['friend'] = friend
        if self.cmd_frag[0] == 'list-invite' and not status:
            # Cause invite could be a null list
            resp['invite'] = invite

        return json.dumps(resp)

    @staticmethod
    def createRandomToken():
        return hashlib.sha256(str(random.random()).encode('UTF-8')).hexdigest()

    def checkToken(self):
        try:
            user = User.select().where(User.token == self.cmd_frag[1])
        except:
            return None
        if not user:
            print('XXX: Not login yet')
            return None
        if len(user) > 1:
            print('!!!: Multiple users')
        return user[0]

    def cmdProcess(self):
        self.cmd_frag = self.cmd_str.split(' ')
        return self.cmd_switch.get(self.cmd_frag[0], self.exception)()

    @print_func_name
    def exception(self):
        print('XXX: Unknown Command')
        return self.createResp(1, message = 'Unknown command '+self.cmd_frag[0])

    @print_func_name
    def register(self):
        # Usage failed
        if len(self.cmd_frag) != 3:
            print('XXX: Usage error')
            return self.createResp(1, message = 'Usage: register <id> <password>')

        username, password = self.cmd_frag[1:3]
        print('Create user: {0}, {1}'.format(username, password))

        # Check if username is used
        if(User.select().where(User.username == username)):
            print('XXX: Username used')
            return self.createResp(1, message = username + ' is already used')
        
        # Create account
        new_user = User.create(
            username = username,
            password = hashlib.sha256(password.encode('UTF-8')).hexdigest()
            )
        print('OOO')
        return self.createResp(0, message = 'Success!')
    
    @print_func_name
    def login(self):
        # Usage failed
        if len(self.cmd_frag) != 3:
            print('XXX: Usage error')
            return self.createResp(1, message = 'Usage: login <id> <password>')
        
        username, password = self.cmd_frag[1:3]
        print('Login user: {0}, {1}'.format(username, password))
        
        # Check user
        user = User.select().where(User.username == username)
        if not user:
            print('XXX: No such user')
            return self.createResp(1, message = 'No such user or password error')
        if len(user) != 1:
            print('!!!: Multiple users')
        user = user[0]

        # Check password
        if hashlib.sha256(password.encode('UTF-8')).hexdigest() != user.password:
            print('XXX: Password doesnt match')
            return self.createResp(1, message ='No such user or password error')
        
        # Create and send Token
        if(not user.token):
            user.token = self.createRandomToken()
            user.save()
        print('OOO: token = ' + user.token)
        return self.createResp(
            0,
            token = user.token,
            message = 'Success!')

    @print_func_name
    def delete(self):
        # Check user
        user = self.checkToken()
        if not user:
            return self.createResp(1, message = 'Not login yet')

        # Usage failed
        if len(self.cmd_frag) != 2:
            print('XXX: Usage error')
            return self.createResp(1, message = 'Usage: delete <user>')
        
        # Delete user-related data 
        user.delete_instance(recursive = True) #Fucking EZ!!
        print('OOO')
        return self.createResp(0, message = 'Success!')
    
    @print_func_name
    def logout(self):
        # Check user
        user = self.checkToken()
        if not user:
            return self.createResp(1, message = 'Not login yet')
        
        # Usage failed
        if len(self.cmd_frag) != 2:
            print('XXX: Usage error')
            return self.createResp(1, message = 'Usage: logout <user>')
        

        # Clear token
        user.token = None
        user.save()
        print('OOO')
        return self.createResp(0, message = 'Bye!')

    @print_func_name
    def invite(self):
        # Check sender
        sender = self.checkToken()  
        if not sender:
            print('XXX: Not login yet')
            return self.createResp(1, message = 'Not login yet')
        
        # Usage error
        if len(self.cmd_frag) != 3:
            print('XXX: Usage error')
            return self.createResp(1, message = 'Usage: invite <user> <id>')
        

        recver_name = self.cmd_frag[2]
        # Check receiver
        recver = User.select().where(User.username == recver_name)
        if not recver:
            print('XXX: No such recver ')
            return self.createResp(1, message = recver_name + ' does not exist')
        recver = recver[0]
        
        # Who is receiver?
        if recver == sender:
            print('XXX: Invite self')
            return self.createResp(1, message = 'You cannot invite yourself')
        
        # Already friend?
        is_sender_smaller = sender.id < recver.id 
        friends = sender.friends_1 if is_sender_smaller else sender.friends_2
        for pair in friends:
            tar = pair.friend_2 if is_sender_smaller else pair.friend_1
            if tar == recver:
                print('XXX: Already friends')
                return self.createResp(
                    1,
                    message = recver.username + ' is already your friend'
                )
        
        # Already invited?
        old_invites = sender.send_invites
        for invite in old_invites:
            if invite.receiver == recver:
                print('XXX: Already invited')
                return self.createResp(1, message = 'Already invited')
        
        # Already received?
        old_invites = sender.recv_invites
        for invite in old_invites:
            if invite.sender == recver:
                print('XXX: Already received invitation')
                return self.createResp(
                    1,
                    message = recver.username + ' has invited you'
                )
        
        # Send invitaion .. finally = =
        FriendInvite.create(sender = sender, receiver = recver)
        print('OOO')
        return self.createResp(0, message = 'Success!')

    @print_func_name
    def listInvt(self):
        # Check user
        user = self.checkToken()
        if not user:
            print('XXX: Not login yet')
            return self.createResp(1, message = 'Not login yet')

        # Usage error
        if len(self.cmd_frag) != 2:
            print('XXX: Usage error')
            return self.createResp(1, message = 'Usage: list-invite <user>')

        # List
        invites = list(map(lambda x:x.sender.username, user.recv_invites))
        print('OOO')
        return self.createResp(0, invite = invites)
    
    @print_func_name
    def acptInvt(self):
        # Check user
        user = self.checkToken()
        if not user:
            print('XXX: Not login yet')
            return self.createResp(1, message = 'Not login yet')

        # Usage error
        if len(self.cmd_frag) != 3:
            print('XXX: Usage error')
            return self.createResp(1, message = 'Usage: accept-invite <user> <id>')

        sender_name = self.cmd_frag[2]
        # Check if invited
        invite = FriendInvite.select().where(FriendInvite.receiver == user)
        
        is_invite = False
        for i, inv in enumerate(invite):
            if inv.sender.username == sender_name:
                invite = invite[i]
                is_invite = True
                break

        if not is_invite:
            print('XXX: Not invited')
            return self.createResp(
                1,
                message = sender_name + ' did not invite you'
            )
        sender = invite.sender
        
        # Create friend and Remove invitation
        if sender.id < user.id:
            FriendPair.create(
                friend_1 = sender,
                friend_2 = user
            )
        else:
            FriendPair.create(
                friend_1 = user,
                friend_2 = sender
            )
        invite.delete_instance()
        print('OOO')
        return self.createResp(0, message = 'Success!')

        
    @print_func_name
    def listFrnd(self):
        # Check user
        user = self.checkToken()
        if not user:
            print('XXX: Not login yet')
            return self.createResp(1, message = 'Not login yet')

        # Usage error
        if len(self.cmd_frag) != 2:
            print('XXX: Usage error')
            return self.createResp(1, message = 'Usage: list-friend <user>')
        
        # List
        friends = list(map(lambda x: x.friend_2.username, user.friends_1))\
                + list(map(lambda x: x.friend_1.username, user.friends_2))
        print('OOO')
        return self.createResp(0, friend = friends)
    
    @print_func_name
    def post(self):
        # Check user
        user = self.checkToken()
        if not user:
            print('XXX: Not login yet')
            return self.createResp(1, message = 'Not login yet')
        
        # Usage error
        if len(self.cmd_frag) < 3:
            print('XXX: Usage error')
            return self.createResp(1, message = 'Usage: post <user> <message>')

        # Create post
        Post.create(user = user, text = ' '.join(self.cmd_frag[2:]))
        print('OOO')
        return self.createResp(0, message = 'Success!')
    
    @print_func_name
    def recvPost(self):
        # Check user
        user = self.checkToken()
        if not user:
            print('XXX: Not login yet')
            return self.createResp(1, message = 'Not login yet')
        
        # Usage error
        if len(self.cmd_frag) != 2:
            print('XXX: Usage error')
            return self.createResp(1, message = 'Usage: receive-post <user>')
        
        # List
        friends = list(map(lambda x: x.friend_2, user.friends_1))\
                + list(map(lambda x: x.friend_1, user.friends_2))
        posts = []
        for f in friends:
            for post in f.posts:
                posts.append(
                    {
                    'id': f.username,
                    'message': post.text
                    }
                )
        print('OOO: {0} posts'.format(len(posts)))
        return self.createResp(0, post = posts)

    ########## HW4 ##########

    @staticmethod
    def sendAMQ(dest, msg):
        conn = stomp.Connection()
        conn.connect()
        conn.send(dest, msg)
        conn.disconnect()

    @print_func_name
    def sendMsg(self):
        # Check user
        user = self.checkToken()
        if not user:
            print('XXX: Not login yet')
            return self.createResp(1, message = 'Not login yet')
        
        # Usage error
        if len(self.cmd_frag) != 4:
            print('XXX: Usage error')
            return self.createResp(1, message = 'Usage: send <user> <friend> <message>')
        
        # Receiver exists?
        recver = User.select().where(User.username == self.cmd_frag[2])
        if not recver:
            print('XXX: No such recver')
            return self.createResp(1, message = 'No such user exist')
        recver = recver[0]

        # Is user's friend?
        if user.id < recver.id:
            fp = FriendPair.select().where(
                (FriendPair.friend_1 == user) &
                (FriendPair.friend_2 == recver))
        else:
            fp = FriendPair.select().where(
                (FriendPair.friend_1 == recver) &
                (FriendPair.friend_2 == user))
        if not fp:
            print('XXX: Is not friend')
            return self.createResp(1, message = self.cmd_frag[2] + ' is not your friend')
        
        # Receiver offline
        if not recver.token:
            print('XXX: Recver offline')
            return self.createResp(1, message = self.cmd_frag[2] + ' is not online')
        
        # Send message
        self.sendAMQ(
            '/queue/'+recver.token, 
            '<<<{0}->{1}: {2}>>>'.format(user.username, self.cmd_frag[2], self.cmd_frag[3]))
        return self.createResp(1, message = 'Success!')
        

    @print_func_name
    def crtGrp(self):
        pass
    
    @print_func_name
    def listGrp(self):
        pass
    
    @print_func_name
    def listJoined(self):
        pass
    
    @print_func_name
    def joinGrp(self):
        pass
    
    @print_func_name
    def sendGrp(self):
        pass
    


# main
if len(sys.argv) < 2 or len(sys.argv) > 3:
    print('Usage: python3 <program.py> <Host> <Port>')
    exit(0)
elif len(sys.argv) == 2:
    host = socket.INADDR_LOOPBACK
    port = sys.argv[1]
else:
    host, port = sys.argv[1:3]
    
server = Server(str(host), int(port))
server.run()