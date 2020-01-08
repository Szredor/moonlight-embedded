#! /usr/bin/env python3

'''
    Main functionality: Turn on and off VMs when some client logs in or out
    
    - create new work machines for new users
    - run as many gaming machines as users are logged in
'''

import libvirt
import bisect
import sys
import sqlite3
import logging
import logging.config

import users
import hypervisor
import database

#version
__vers__ = '0.1'

#name of database with logins
db_name = "moonlight_users.db"

#List of table which have to be in database
#Used in autocreation process
#(name, sql)
table_list = [("Users", "CREATE TABLE Users (user_id integer primary key autoincrement, username varchar(32), password varchar(32), permission integer)")]

#list of User objects
user_status = []
user_count = 0

max_gaming_count = 1

def execute_query(cmd):
    try:
        cur.execute(cmd)
    
        if cmd.upper().startswith("SELECT"):
            rows = cur.fetchall()
            if not rows == None:
                return rows
            else:
                return None
    except sqlite3.Error as e:
        print ("Error:", e.args[0])      

def log_user_in(username, password):
    global hyper
    global cur
    
    client = ["", username, password, ""]
    
    #looking for user in database
    log.info("looking for user in database...")
    try:
        param = (username, password)
        log.debug("query...")
        cur.execute('select user_id, permission from Users where username=? and password=?', param)
        log.debug("...query done")
        user = cur.fetchone()
        
        if user == None:
            log.debug("user not found - raising exception")
            print ('Wrong username or password')
            raise database.DatabaseError("Wrong username or password.", database.DatabaseError.USER_DOESNT_EXIST)
        else:
            client[0] = user[0]#user_id
            client[3] = user[1]#permission
            log.debug("user found: %s", client)
    except sqlite3.Error as e:
        log.exception("sqlite3 error: %s", e.args[0])
    else:
        global user_count
        user_count+=1
        log.debug("user_count after change: %s", user_count)
        
        #create his status in list
        log.info("creating user status and inserting into list")
        usr = users.User(client[1], client[0], client[3])
        bisect.insort_right(user_status, usr)
        
        #user's work domain
        log.info("work domain...")
        try:
            hyper.startup_name(usr.work_domain_name)
        except hypervisor.DomainError as e:
            log.debug(e.get_message())
        
        #gaming domain
        log.info("gaming domain...")
        if user_count <= max_gaming_count:
            #find one shutted down and run it
            try:
                name = hyper.find_gaming_domain_down(max_gaming_count, user_count)
                hyper.startup_name(name)
            except hypervisor.DomainError as e:
                log.exception(e.get_message())            
        else:
            log.warning("all gaming domains are up")
        
        log.info("user "+usr.username+' has succefully logged in')

def log_user_out (usr):
    global user_count
    global hyper
    
    name = usr.username
    
    #left every domain
    #User could drop the connection to the server, and in this case server has to force shutdown of the domains
    usr.prepare_logout()
    
    #send shutdown flag to his work_domain
    log.info("work domain...")
    try:
        hyper.shutdown_name(usr.work_domain_name)
    except hypervisor.DomainError as e:
        log.exception(e.get_message())
    
    #shutdown one gaming domain if its necessary
    log.info("gaming domain...")
    if user_count - 1 < max_gaming_count:
        try:
            status = hyper.find_empty_gaming_status()
            hyper.shutdown_name(status.name)
        except hypervisor.DomainError as e:
            log.exception(e.get_message())        
    else:
        log.info("it is unnecessary to shutdown one gaming domain")
    
    user_count-=1
    log.debug("user_count after change: %s", user_count)
    user_status.remove(usr)
    log.info("removing user's status")
    log.info('user '+name+' has succesfully logged out')

def register_user(username, password, permission = 1):
    para = (username,)
    cur.execute('select user_id from Users where username=?', para)    
    user = cur.fetchone()
    
    if user != None:
        raise database.DatabaseError("There is already such an user!", database.DatabaseError.USER_EXISTS)
    
    para = (username, password, permission)
    cur.execute("INSERT INTO Users(user_id, username, password, permission) VALUES (NULL, ?, ?, ?)", para)
    user_db.commit()
    
    #create a work domain with his/her username
    hyper.create_work_domain(username)

def shutdown():
    log.info("starting shutdown...")
    
    if hyper != None: hyper.close()
    
    log.info("closing connection to database")  
    cur.close()
    log.debug("cursor: closed")
    user_db.close()
    log.debug("database: closed")
    log.info("connection to database closed")
    log.info("shutdown done")
    exit(0)
    
# ==========
# == MAIN ==
# ==========

#logging module configuration
logging.config.fileConfig('logs/log.conf', disable_existing_loggers=False)
log = logging.getLogger(__name__)
log.info("starting up server software - vers: %s", __vers__)

log.debug("config:")
log.debug("max_gaming_count: %s", max_gaming_count)
log.debug("table_list: \n%s", table_list)
log.debug("db_name: %s", db_name)


#connection to database
log.info("connecting to database: %s", db_name)
try:
    user_db = sqlite3.connect(db_name)
    log.debug("databse object: OK")
    cur = user_db.cursor()
    log.debug("cursor object: OK")
except sqlite3.Error as e:
    log.exception("sqlite3 error: %s", e.args[0])
else:
    log.info("database connection: OK")

#checking if there are all tables
#create if some dont excist
#and warn when some table is not the same as blueprint
log.info("checking tables...")
log.debug("executing query...")
cur.execute("select tbl_name, sql from sqlite_master where type = 'table'")
log.debug("...query done")
tables = cur.fetchall()
for blueprint in table_list:
    log.debug("looking for: %s", blueprint)
    num = tables.count(blueprint)
    log.debug("found num: %s", num)
    if num == 0:
        log.warning("there is no table named "+blueprint[0]+" - create one")
        cur.execute(blueprint[1])
    elif num > 1:
        log.error("there is an error in database - too many tables with name "+blueprint[0])
    else:
        log.info("table "+blueprint[0]+" OK")

#connection to hypervisor
log.info("starting Hypervisor object...")
hyper = hypervisor.Hypervisor()
if hyper.is_critical():
    shutdown()
log.info("...Hypervisor object OK")

#getting all defined gaming domains
#work doamins are unnecessary to find, because until somebody not logs in, it wont be needed
#check if there are all gaming domains
log.info("checking number of gaming domains...")
gam_names = []
for i in range(max_gaming_count):
    gam_names.append("g"+str(i))
    log.debug("adding g"+str(i))
if len(hyper.find_domains_names(gam_names)) == max_gaming_count:
    log.info ("gaming domains: OK")
elif len(hyper.find_domains_names(gam_names)) == 0:
    log.critical("There are no gaming domains registered - server cant work properly")
    shutdown()
else:
    log.error("there is a lack of gaming domains")

log.info("server started")

choose = 1
while choose is not 0:
    print ("Choose action:")
    print ("1. login")
    print ("2. logout")
    print ("3. use g-domain")
    print ("4. left g-domain")
    print ("5. use w-domain")
    print ("6. left w-domain")
    print ("7. register new user")
    print ("8. users list")
    print ("9. domains status list")
    print ("0. exit")
    choose = int(input())
    log.debug("menu choose: %s", choose)
    if choose == 1:
        login = str(input("Login:"))
        passwd = str(input("Pass:"))
        
        try:
            log.info("starting login procedure...")
            log_user_in(login, passwd)
            log.info("...login procedure done")
        except database.DatabaseError as e:
            log.exception(e.get_message())
    elif choose == 2:
        i = 1
        for user in user_status:
            print (str(i)+".", user)
            i+=1
        
        i = int(input())-1
        if i >= 0 and i <= len(user_status):
            log.info("starting logout procedure...")
            log_user_out(user_status[i])
            log.info("...logout procedure done")
        else: print("Out of Range. Again.")
    elif choose == 3:
        log.info("someone want to use gaming domain")
        i = 1
        for user in user_status:
            print (str(i)+".", user)
            i+=1
        index = int(input()) - 1
        usr = user_status[index]
        log.info("user: %s", usr.username)
        
        #change flags of user and domain
        log.info("changing flags...")
        try:
            #it should be raised earlier than finding domain, because method to flag playing needs a status obj
            #its little dirty workaroud, but works
            state = usr.get_state()
            log.debug("user's state: %s", state)
            if state == users.User.USE_GAMING_DOMAIN or state == users.User.USE_BOTH_DOMAINS:
                raise users.UserError(usr.username + " is playing already", users.UserError.IS_PLAYING)
            
            #find empty gaming domain
            status = hyper.find_empty_gaming_status()
            log.debug("found gaming domain status: %s", status)
            #this if is just for sure, but its unnecessary
            if status.using == True:
                raise hypervisor.DomainError(status.user + " is using " + status.name + " already.", False, hypervisor.DomainError.IS_OCCUPIED)
            
            usr.use_gaming_domain(status)
        except hypervisor.DomainError as e:
            log.debug(e.get_message())
            log.info ("user "+usr.username+" doesnt change the state")
        except users.UserError as e:
            log.debug(e.get_message())
            log.info ("user "+usr.username+" doesnt change the state")
            
    elif choose == 4:
        log.info("somebody want to left gaming domain")
        i = 1
        for user in user_status:
            print (str(i)+".", user)
            i+=1
        index = int(input()) - 1
        usr = user_status[index]
        log.info("user: %s", usr.username)
                
        #flags
        log.info("changing flags...")
        try:
            usr.left_gaming_domain()
        except users.UserError as e:
            log.debug(e.get_message())
            log.info("user "+usr.username+" doesnt change the state")
    elif choose == 5:
        log.info("someone want to use work domain")
        i = 1
        for user in user_status:
            print (str(i)+".", user)
            i+=1
        index = int(input()) - 1
        usr = user_status[index]
        log.info("user: %s", usr.username)
        
        #set flags for using work domain
        log.info("changing flags...")
        try:
            status = hyper.find_work_status(usr.work_domain_name)
            log.debug("work domain status: %s", status)
            if status.using == True:
                raise hypervisor.DomainError(status.user + " is using " + status.name + " already.", False, hypervisor.DomainError.IS_OCCUPIED)
            usr.use_work_domain(status)
        except hypervisor.DomainError as e:
            log.debug(e.get_message())
            if e.get_code == hypervisor.DomainError.IS_NOT_RUNNING:
                #so boot it up
                hyper.startup_name(usr.work_domain_name)
            log.info("user "+usr.username+" doesnt change the state")
        except users.UserError as e:
            log.debug(e.get_message())
            log.info("user "+usr.username+" doesnt change the state")           
    elif choose == 6:
        log.info("someone wants to left work domain")
        i = 1
        for user in user_status:
            print (str(i)+".", user)
            i+=1
        index = int(input()) - 1
        usr = user_status[index]
        log.info("user: %s", usr.username)
        
        #flags
        log.info("changing flags...")
        try:
            usr.left_work_domain()
        except users.UserError as e:
            log.debug(e.get_message())
            log.info("user "+usr.username+" doesnt change the state")
    elif choose == 7:
        log.info("someone wants to register")
        log.debug("taking data...")
        print ("Insert username and password of new user:")
        username = str(input("Login:"))
        password = str(input("Password:"))
        re_password = str(input("Repeat password:"))
        while password != re_password:
            print ("Passwords are not valid.")
            password = str(input("Password:"))
            re_password = str(input("Repeat password:"))
        try:
            log.debug("data taken: "+username+', '+password)
            log.info("starting registration procedure...")
            register_user(username, password)
        except database.DatabaseError as e:
            log.exception(e.get_message())
        else:
            log.info("user " + username + " successfully registered")
    elif choose == 8:
        for usr in user_status:
            print (usr)
    elif choose == 9:
        hyper.list_status()
    elif choose == 0:
        shutdown()
    else: pass

