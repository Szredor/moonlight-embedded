#! /usr/bin/env python3

import logging

class UserError (Exception):
    #codes
    DOMAIN_NOT_FOUND = 1
    IS_ALREADY_USING = 2
    IS_NOT_WORKING = 3
    IS_WORKING = 4
    IS_PLAYING = 5
    IS_NOT_PLAYING = 6
    
    def __init__ (self, message, code):
        self.__message = message
        self.__code = code
    
    def get_code(self):
        return self.__code
    
    def get_message(self):
        s = "UserError : " + self.__message
        return s
    

class User:
    #flags
    LOGGED_IN = 0
    USE_GAMING_DOMAIN = 1
    USE_WORK_DOMAIN = 2
    USE_BOTH_DOMAINS = 3
    
    def __init__(self, usr, u_id, permission):
        self.__log = logging.getLogger(__name__)
        self.username = usr
        self.__log_signed("constructing User object")
        self.__state = User.LOGGED_IN
        self.__using_work_status = None
        self.__using_gaming_status = None
        
        self.user_id = u_id
        self.permission = permission
        self.work_domain_name = "win-work-"+usr
    
    def __lt__ (self, other):
        return self.username < other.username
    
    def __repr__(self):
        return self.username + "\nstatus: " + str(self.__state) + "\nusing domains:\nwork: " + str(self.__using_work_status) + "\ngaming: " + str(self.__using_gaming_status) 
    
    def __log_signed(self, msg, lvl='info'):
        real_msg = "user: "+self.username + " - " + msg
        if lvl == 'info': self.__log.info(real_msg)
        elif lvl == 'debug': self.__log.debug(real_msg)
        elif lvl == 'exception': self.__log.exception(real_msg)
        elif lvl == 'warning': self.__log.warning(real_msg)
        else: self.__log.critical(real_msg)
    
    def get_state(self):
        return self.__state
    
    def use_work_domain(self, status):
        self.__log_signed("changing flags for using work domain")
        if self.__state == User.USE_GAMING_DOMAIN:
            self.__state = User.USE_BOTH_DOMAINS
        elif self.__state == User.LOGGED_IN:
            self.__state = User.USE_WORK_DOMAIN
        else:
            raise UserError(self.username + " is working already", UserError.IS_WORKING)
        
        self.__log_signed("adding data to using domain status")
        self.__using_work_status = status
        self.__using_work_status.user = self.username
        self.__using_work_status.using = True
        
        self.__log_signed("started using "+self.__using_work_status.name+" properly")
    
    def left_work_domain(self):
        self.__log_signed('changing flags for leaving work status')
        if self.__state == User.USE_BOTH_DOMAINS:
            self.__state = User.USE_GAMING_DOMAIN
        elif self.__state == User.USE_WORK_DOMAIN:
            self.__state = User.LOGGED_IN
        else:
            raise UserError(self.username + " is not working in any domain now", UserError.IS_NOT_WORKING)
        
        self.__log_signed('changnig data into using domain status')
        self.__using_work_status.using = False
        self.__using_work_status.user = None
        self.__log_signed("stopped using "+self.__using_work_status.name+' properly')
        self.__using_work_status = None
        
    def use_gaming_domain(self, status):
        self.__log_signed("changing flags for using gaming domain")
        if self.__state == User.USE_WORK_DOMAIN:
            self.__state = User.USE_BOTH_DOMAINS
        elif self.__state == User.LOGGED_IN:
            self.__state = User.USE_GAMING_DOMAIN
        else:
            raise UserError(self.username + " is playing already", UserError.IS_PLAYING)
        
        self.__log_signed("adding data to using domain status")
        self.__using_gaming_status = status
        self.__using_gaming_status.user = self.username
        self.__using_gaming_status.using = True
        self.__log_signed("started using "+self.__using_gaming_status.name+" properly")
    
    def left_gaming_domain(self):
        self.__log_signed('changing flags for leaving gaming status')
        if self.__state == User.USE_BOTH_DOMAINS:
            self.__state = User.USE_WORK_DOMAIN
        elif self.__state == User.USE_GAMING_DOMAIN:
            self.__state = User.LOGGED_IN
        else:
            raise UserError(self.username + " is not playing in any domain now", UserError.IS_NOT_PLAYING)
        
        self.__log_signed('changnig data into using domain status')
        self.__using_gaming_status.using = False
        self.__using_gaming_status.user = None
        self.__log_signed("stopped using "+self.__using_gaming_status.name+' properly')
        self.__using_gaming_status = None
    
    def prepare_logout(self):
        self.__log_signed('preparing flags for logout')
        if self.__state == User.USE_BOTH_DOMAINS:
            self.left_gaming_domain()
            self.left_work_domain()
        elif self.__state == User.USE_GAMING_DOMAIN:
            self.left_gaming_domain()
        elif self.__state == User.USE_WORK_DOMAIN:
            self.left_work_domain()
        
            
        
        
        
    