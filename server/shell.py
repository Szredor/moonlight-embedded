#!/usr/bin/env python3
#Shell threads

import threading
import pickle
import queue
import socket
import logging
import time
import os

from resources import Package, thread_blu


class Shell():
    #This thread just listens and waits for clients info 
    class listening_thread(threading.Thread, thread_blu):
        def __init__(self, name, threadID, q, srv_ip, port):
            #
            threading.Thread.__init__(self)     
            thread_blu.__init__(self, name, threadID)
            
            self.__q = q
            
            self._log.info("starting Listening Thread: %s", self.name)
            
            
            self.__IP = ""
            self.__PORT = port
            self.__srv_ip = (self.__IP, self.__PORT)
            
        def run(self):
            self._log.info("binding socket on port %s", self.__PORT)
            srv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            srv_sock.bind(self.__srv_ip)
            
            while Shell._running:
                self._log.debug("receiving...")
                data, addr = srv_sock.recvfrom(1024)
                
                pack = pickle.loads(data)
                
                #checking all posibilities
                if type(pack) is Package:
                    pack.set_from(addr[0])
                    
                    self._log.debug(pack)
                    self.__q.put(pack)
                elif type(pack) == dict :
                    if pack["__class__"] == 'ConsoleApplication1.Program+Package':
                        self._log.debug("Received data is a Package")
                        rec_pack = Package(pack["TO"], pack["data"], pack["personality"])
                        rec_pack.set_from(addr[0])
                        
                        self._log.debug(rec_pack) 
                        self.__q.put(rec_pack)
                    else:
                        self._log.warning("Wrong Package from %s", addr)                
                else:
                    self._log.warning("Wrong Package from %s", addr)
            
            self._log.info("exiting Listening Thread: %s ", self.name)
            #thread_blu._end(self)

    class sender_thread(threading.Thread, thread_blu):
        def __init__(self, name, threadID, q, srv, port):
            threading.Thread.__init__(self)
            thread_blu.__init__(self, name, threadID)
            
            self.__q = q
            
            self._log.info("starting Sender Thread: %s", self.name)
            
            self.__PORT = port
            self.__IP = srv
            self.__srv_ip = (self.__IP, self.__PORT)
        
        def run(self):
            send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            while Shell._running:
                time.sleep(0.01)
                if not self.__q.empty():
                    pack = self.__q.get_nowait()
                    self.__q.task_done()
                    pick = pickle.dumps(pack)
                    self._log.debug("sending %s to %s", pack, pack.TO)
                    send_sock.sendto(pick, (pack.TO, self.__PORT))
                    
            
            self._log.info("exiting Sender Thread: %s", self.name)
                    
    class keyboard_input_thread(threading.Thread, thread_blu):
        def __init__(self, name, threadID, q, srv, port, user_status):
            threading.Thread.__init__(self)
            thread_blu.__init__(self, name, threadID)
            
            self._log.info("starting Keyboard Input Thread: %s", self.name)
            
            self.__q = q
            self.__user_status = user_status
            self.__cli_text = ""
            
            self.__PORT = port
            self.__IP = srv
            self.__srv_ip = (self.__IP, self.__PORT)            
            
        def run(self):
            f = open("cli.txt", "r")
            self.__cli_text = f.read()
            f.close()
            
            while Shell._running:                
                pack = self.__cli_choose()
                self._log.info("package succefully created in cli")
                self._log.debug(pack)
                
                if pack is not None:
                    pack.set_from(self.__srv_ip)
                    self.__q.put(pack)
                    if pack.data[0] == 0:
                        time.sleep(2)
            
            self._log.info("exiting Keyboard Input Thread: %s", self.name)
            
        def __choose_user(self):
            i = 1
            for user in self.__user_status:
                print (str(i)+".", user)
                i+=1
            
            i = int(input())-1
            if i >= 0 and i <= len(self.__user_status):
                usr = self.__user_status[i]
                return usr
            
            print("Out of Range. Again.")
            return None            
            
        def __cli_choose(self):
            self._log.info("statring cli choose on server")
            ls = []
            
            print (self.__cli_text)
            
            try:
                choose = int(input())
            except ValueError as e:
                print ("Value should be integer.")
                return None
            ls.append(choose)
            if choose == 1:#(login(str), pass(str))
                login = str(input("Login: "))
                passwd = str(input("Password: "))
                ls.append(login)
                ls.append(passwd)
            elif choose == 2 or choose == 3 or choose == 4 or choose == 5 or choose == 6:#(User obj)
                usr = self.__choose_user()
                if usr is not None:
                    ls.append(usr.user_id)
                else:
                    return None
            elif choose == 7:#(login, pass)
                print ("Insert username and password of new user:")
                username = str(input("Login:"))
                password = str(input("Password:"))
                re_password = str(input("Repeat password:"))
                while password != re_password:
                    print ("Passwords are not valid.")
                    password = str(input("Password:"))
                    re_password = str(input("Repeat password:"))
                ls.append(username)
                ls.append(password)
            else: pass
            
            if len(ls):
                return Package(self.__IP, ls)
            else:
                return None
            
    def __init__(self, srv, port, user_status):
        Shell._running = True
        Shell._exititng = False
        Shell._started = False
        
        self.__log = logging.getLogger(__name__)
        
        self.__log.info("starting Shell __init__()")
        
        counter = 0
        self.__threads_names = ["LISTEN", "SENDER", "CLI"]
        self.__threads_list = []
        
        #thread pools
        self.__incoming_queue = queue.Queue()
        self.__outcoming_queue = queue.Queue()
        
        self.__log.info("preparing threads to start...")
        try:
            #Initialization of Threads
            listening = self.listening_thread(self.__threads_names[counter], counter, self.__incoming_queue, srv, port)
            listening.daemon = True
            self.__threads_list.append(listening)
            counter += 1

            sender = self.sender_thread(self.__threads_names[counter], counter, self.__outcoming_queue, srv, port)
            sender.daemon = True
            self.__threads_list.append(sender)
            counter += 1

            cli = self.keyboard_input_thread(self.__threads_names[counter], counter, self.__incoming_queue, srv, port, user_status)
            cli.daemon = True
            self.__threads_list.append(cli)
            counter +=1

            for t in self.__threads_list:
                t.start()
        except RuntimeError as e:
            self.__log.exception(e)
        else:
            self.__log.info("All threads initialized")
            Shell._started = True
            self.__log.info("Shell __init__() done")
        
    def exit(self):
        Shell._running = False
        Shell._exititng = True
        self.__log.info("exiting Shell")
        
        self.__log.info("There are %s threads still running", len(self.__threads_list))
        self.__log.info("Shell exit done")
    
    def is_running(self):
        if Shell._running and Shell._started: return True
        return False
    
    def get_packet(self):
        if self.__incoming_queue.empty():
            return None
        pack = self.__incoming_queue.get_nowait()
        self.__incoming_queue.task_done()
        return pack
    
    def push_packet(self, pack):
        self.__outcoming_queue.put(pack)
        
        
