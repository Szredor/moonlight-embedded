#! /usr/bin/env python3

class DatabaseError (Exception):
    #codes
    USER_EXISTS = 1
    USER_DOESNT_EXIST = 2
    
    def __init__ (self, message, code):
        self.__message = message
        self.__code = code
    
    def get_code(self):
        return self.__code
    
    def get_message(self):
        s = "DatabaseError : " + self.__message
        return s    