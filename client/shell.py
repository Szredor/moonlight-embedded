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
        def __init__(self, name, threadID, q, port):
            #
            threading.Thread.__init__(self)     
            thread_blu.__init__(self, name, threadID)
            
            self.__q = q
            
            self._log.info("starting Listening Thread: %s", self.name)
            
            
            self.__IP = ""
            self.__PORT = port
            self.__IP_TUPPLE = (self.__IP, self.__PORT)
            
        def run(self):
            self._log.info("binding socket on port %s", self.__PORT)
            srv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            srv_sock.bind(self.__IP_TUPPLE)
            
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
        def __init__(self, name, threadID, q, port):
            threading.Thread.__init__(self)
            thread_blu.__init__(self, name, threadID)
            
            self.__q = q
            
            self._log.info("starting Sender Thread: %s", self.name)
            
            self.__PORT = port
            
        
        def run(self):
            #self.__IP = self.__search_server(self.__PORT)
            self.__IP = "192.168.0.90"
            self.__srv_ip = (self.__IP, self.__PORT)            
            send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            while Shell._running:
                time.sleep(0.01)
                if not self.__q.empty():
                    pack = self.__q.get_nowait()
                    self.__q.task_done()
                    self._log.debug("sending %s to %s", pack, pack.TO)
                    send_sock.sendto(pickle.dumps(pack), (pack.TO, self.__PORT))
                    self._log.debug("sent")
                    
            
            self._log.info("exiting Sender Thread: %s", self.name)
        
        def search_server(self, port):
            pass
                    
    def __init__(self, srv, port):
        Shell._running = True
        Shell._exititng = False
        Shell._started = False
        
        self.__log = logging.getLogger(__name__)
        
        self.__log.info("starting Shell __init__()")
        
        counter = 0
        self.__threads_names = ["LISTEN", "SENDER"]
        self.__threads_list = []
        
        #thread pools
        self.__incoming_queue = queue.Queue()
        self.__outcoming_queue = queue.Queue()
        
        self.__log.info("preparing threads to start...")
        try:
            #Initialization of Threads
            listening = self.listening_thread(self.__threads_names[counter], counter, self.__incoming_queue, port)
            listening.daemon = True
            self.__threads_list.append(listening)
            counter += 1

            sender = self.sender_thread(self.__threads_names[counter], counter, self.__outcoming_queue, port)
            sender.daemon = True
            self.__threads_list.append(sender)
            counter += 1

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
        if type(pack) == Package:
            self.__outcoming_queue.put(pack)
            
        
        
