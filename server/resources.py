#!/usr/bin/env python3
import time
import logging
# Basic server resources

class Package():
    SLAVE = 0
    USER = 1
    SERVER = 2
    SU = 3

    def __init__(self, to, data, personality = 2):
        self.TO = to #string IP
        if type(data) == list or type(data) == tuple:
            self.data = data #list (choose, args*)
        else:
            self.data = None
        self.FROM = None #string IP - set after receiving
        self.errcode = 0 #int
        self.personality = personality #int

    def set_from(self, IP):
        self.FROM = IP

    def __repr__(self):
        return "TO: "+str(self.TO)+" - DATA: "+str(self.data)+" - FROM: "+str(self.FROM)+" - PERSONALITY: "+str(self.personality)

#Blueprint of my threads
class thread_blu():
    def __init__(self, name, threadID):
        self.threadID = threadID
        self.name = str(name)
        self._log = logging.getLogger(self.name)

    #def _end(self):
        #self.__tl.remove(self)
        #threading.current_thread().end
        
def disassemble(cmd):
    if len(cmd) == 0: return
    
    last = 0
    cmds = []
    x=0

    while cmd[x] == ' ': x+=1
    for i in range(x, len(cmd)-1):
        if cmd[i] == ' ' and cmd[i-1] == ' ':
            last = i+1
        elif cmd[i] == ' ':
            cmds.append(cmd[last:i])
            last = i+1
    
    if not cmd[-1] == ' ': cmds.append(cmd[last:len(cmd)])
    return cmds
            
        
