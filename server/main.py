#! /usr/bin/env python3

'''
    Main functionality: Turn on and off VMs when some client logs in or out
    
    - create new work machines for new users
    - run as many gaming machines as users are logged in
'''

import libvirt
import bisect
import sys
import os
import sqlite3
import logging
import logging.config
import time
import threading

import users
import hypervisor
import database
import shell
from resources import Package

if os.getuid() != 0:
    print("Please run this program with superuser privileges")
    exit(1)

#version
__vers__ = '0.2'
config_filepath = 'srv_config.conf'

#default configs dictionary
config = dict()

config['vm_path'] = "/home/vm/VM/"
config['disks_path'] = "Disks/"
config['blank_disks'] = "Disks/blank/"
config['blank_work_disk_name'] = "win_work.qcow2"
config['new_work_domain_xml'] = "~/VM/blank_work_domain.xml"

config['log_conf_path'] = 'logs/log.conf'

#ip configs
config['server_ip'] = "10.0.10.92"
config['port'] = 57201

#name of database with logins
config['users_db_path'] = "moonlight_users.db"

#List of table which have to be in database
#Used in autocreation process
#(name, sql)
table_list = [("Users", "CREATE TABLE Users (user_id integer primary key autoincrement, username varchar(32), password varchar(32), permission integer)")]

#list of User objects
user_status = []
user_count = 0

#number of gaming sessions named g0,g1,...,gn-1
config['gaming_sessions_number'] = 1
config['gaming_session_prefix'] = 'g'


finish = False
timeout_feed = []
def parse_config(filename, configs):
    conf = open(filename, 'r')

    line = conf.readline()
    
    while line:
        #deleting spaceas on the front
        line = line.lstrip(' ')
        
        #searching for the comment sign and removing text after it
        hash_pos = line.find('#')
        if hash_pos >= 0:
            line = line[0:hash_pos]
        
        if line != '':
            #sign '=' is separator between parameter and iots value
            #if non then parameter is broken
            eq_pos = line.find('=')
            if (eq_pos >= 0):
                param = line[0:eq_pos]
                val = line[eq_pos+1:]
                
                configs[param] = val
        
        line = conf.readline()
    
    conf.close()
    
    return configs

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

def log_user_in(username, password, ip):
    global hyper
    global cur
    
    client = ["", username, password, ""]
    again = False
    
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
            raise database.DatabaseError("Wrong username or password.", database.DatabaseError.USER_DOESNT_EXIST)
        else:
            client[0] = user[0]#user_id
            client[3] = user[1]#permission
            
            #checking if user is logged in already
            #should be binary search but now its linear
            for usr in user_status:
                if usr.user_id == client[0] and usr.ip == ip:
                    #user is back - change his/her domains to unused
                    try:
                        #its useful function to set every domain to unused state
                        usr.prepare_logout()
                    except users.UserError as e:
                        log.exception(e.get_message())
                    log.info("sending back the user id")
                    pack = Package(ip, [1, usr.user_id, max_gaming_count])
                    sh.push_packet(pack)
                    log.info("user "+usr.username+' has succefully logged back in')
                    return 
                elif usr.user_id == client[0]:
                    again = True
                    log.warning("user %s is already logged in", usr.username)
                    
                    #sending feedback
                    pack = Package(ip, [13, "You are already logged in on: "+usr.ip+"\nlogout from there or tell your administartor about the glitch"])
                    sh.push_packet(pack)
            if again == False:
                log.debug("user found: %s", client)
            
                #sending success to the client
                pack = Package(ip, [14, "login success - booting up domains"])
                sh.push_packet(pack)
    except sqlite3.Error as e:
        log.exception("sqlite3 error: %s", e.args[0])
        
        #sending back an exception
        pack = Package (ip, "Server side error - sqlite3")
        pack.errcode = 1
        sh.push_packet(pack)
    else:
        if again == False:
            global user_count
            user_count+=1
            log.debug("user_count after change: %s", user_count)
            
            #create his status in list
            log.info("creating user status and inserting into list")
            usr = users.User(client[1], client[0], client[3], ip)
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
            
            log.info("sending back the user id")
            sh.push_packet(Package(usr.ip, [1, usr.user_id, max_gaming_count]))
            log.info("user "+usr.username+' has succefully logged in')

def log_user_out (user_id):
    global user_count
    global hyper
    
    usr = get_user_obj(user_id)
    if usr == None:
        log.warning("user_id %s is already logged out", user_id)
        return
    
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

def pair_gaming_domain(pack, dom_ip, code):
    nv_pack = Package(dom_ip, [21])
    sh.push_packet(nv_pack)
    nv_count = None
    
    for i in range(6):
        if len(hyper.last_nv_count) > 0 and hyper.last_nv_count[0] == dom_ip:
            nv_count = hyper.last_nv_count[1]
            hyper.last_nv_count = []
        time.sleep(0.2)
    
    if nv_count == None:
        log.error("GE on domain error - hyper.last_nv_count %s", hyper.last_nv_count)
        feed = Package(pack.FROM, [13, "GE on domain error"])
        sh.push_packet(feed)
    elif nv_count == 6 or nv_count == 5:
        code_pack = Package(dom_ip, [20, code])
        sh.push_packet(code_pack)
    elif nv_count != 5 and nv_count != 6:
        log.error("Pairing error - nv_count: %s", nv_count)
        feed = Package(pack.FROM, [13, "Pairing error ("+str(nv_count)+")"])
        sh.push_packet(feed)
        
def get_user_obj(user_id):
    usr = None
    for i in range(len(user_status)):
        if user_status[i].user_id == user_id:
            usr = user_status[i]
            break
    return usr

def shutdown():
    log.info("starting shutdown...")
    log.info("shutting down the timeout check thread...")
    timeout_feed.clear()
    timeout_feed.append("close")
    
    sh.exit()
    
    if hyper != None: hyper.close()
    
    log.info("closing connection to database")  
    cur.close()
    log.debug("cursor: closed")
    user_db.close()
    log.debug("database: closed")
    log.info("connection to database closed")
    log.info("waiting for timeout check...")
    timeout_check_th.join()
    log.info("shutdown done")
    exit(0)
    
# ==========
# == MAIN ==
# ==========

#get all the configuration
config = parse_config(config_filepath, config)

max_gaming_count = int(config['gaming_sessions_number'])

#logging module configuration
logging.config.fileConfig(config['log_conf_path'], disable_existing_loggers=False)
log = logging.getLogger(__name__)
log.info("starting up server software - vers: %s", __vers__)

log.debug("config:")
log.debug("max_gaming_count: %s", max_gaming_count)
log.debug("table_list: \n%s", table_list)
log.debug("db_name: %s", config['users_db_path'])

#creating Shell object
#It is on the begining, because it will capture all the data from the beginning
sh = shell.Shell(config['server_ip'], config['port'], user_status)

#connection to database
log.info("connecting to database: %s", config['users_db_path'])
try:
    user_db = sqlite3.connect(config['users_db_path'])
    log.debug("databse object: OK")
    cur = user_db.cursor()
    log.debug("cursor object: OK")
except sqlite3.Error as e:
    log.exception("sqlite3 error: %s", e.args[0])
else:
    log.info("database connection: OK")

#checking if there are all tables
#create if some doesnt excist
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
hyper = hypervisor.Hypervisor(sh, config)
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

#starting timeout check thread
timeout_check_th = users.TimeoutCheckThread(user_status, timeout_feed, sh, config['server_ip'])
timeout_check_th.start()

log.info("server started")

choose = 1
while choose is not 0:
    time.sleep(0.01)# wait if you want your processor to be alive
    pack = sh.get_packet()
    if pack != None:    
        #pack = sh.get_packet()
        data = pack.data
        choose = data[0]
        
        if choose == 0:
            shutdown()        
        elif choose == 1:#(login(str), pass(str))
            try:
                log.info("starting login procedure...")
                log_user_in(data[1], data[2], pack.FROM)
                log.info("...login procedure done")
            except database.DatabaseError as e:
                log.exception(e.get_message())
                
                #sending back an exception
                pack = Package (pack.FROM, [13, e.get_message()])
                pack.errcode = 1
                sh.push_packet(pack)                
        elif choose == 2:#(User id)
            log.info("starting logout procedure...")
            log_user_out(data[1])
            log.info("...logout procedure done")
        elif choose == 3:#(User id)
            usr = get_user_obj(data[1])
            if usr is not None:
                log.info("user %s wants to use gaming domain", usr.username)
                
                #change flags of user and domain
                log.info("changing flags...")
                try:
                    #it should be raised earlier than finding domain, because method to flag playing domain needs a status obj
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
                        raise hypervisor.DomainError(status.user + " is using " + status.name + " already.", status.gaming, hypervisor.DomainError.IS_OCCUPIED)
                    elif status.booting_up == True:
                        raise hypervisor.DomainError(status.name + "is booting up.", status.gaming, hypervisor.DomainError.IS_BOOTING_UP)
                    usr.use_gaming_domain(status)
                    
                    feed = Package(pack.FROM, [3, status.ip])
                    sh.push_packet(feed)
                except hypervisor.DomainError as e:
                    log.info(e.get_message())
                    feed = None
                    if e.get_code() == hypervisor.DomainError.IS_OCCUPIED:
                        feed = Package(pack.FROM, [13, "Domain "+status.name+" is occupied"])
                    elif e.get_code() == hypervisor.DomainError.IS_BOOTING_UP:
                        feed = Package(pack.FROM, [13, "Domain "+status.name+" is booting up still"])
                    elif e.get_code() == hypervisor.DomainError.EMPTY_NOT_FOUND:
                        feed = Package(pack.FROM, [13, "There is no empty and ready gaming domain"])
                    else:
                        feed = Package (pack.FROM, [13, "user "+usr.username+" doesnt change the state"])
                    sh.push_packet(feed)
                except users.UserError as e:
                    log.debug(e.get_message())
                    log.info (e.get_message())
                    feed = Package (pack.FROM, [13, e.get_message()])
                    sh.push_packet(feed)
            else:
                feed = Package(pack.FROM, [13, "user_id error - not found"])
                sh.push_packet(feed)
                
        elif choose == 4:#(User id)
            usr = get_user_obj(data[1])
            if usr is not None:
                log.info("user %s wants to left gaming domain", usr.username)
                        
                #flags
                log.info("changing flags...")
                try:
                    usr.left_gaming_domain()
                except users.UserError as e:
                    log.debug(e.get_message())
                    log.info("user "+usr.username+" doesnt change the state")
                    feed = Package(pack.FROM, [14, "user "+usr.username+" didn't left gaming domain\nbecause he/she is not playing"])
            else:
                feed = Package(pack.FROM, [13, "user_id error - not found"])
                sh.push_packet(feed)            
        elif choose == 5:#(User id)
            usr = get_user_obj(data[1])
            log.info("user %s wants to use work domain", usr.username)
            
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
                    feed = Package (pack.FROM, [13, "Your work domain is down - booting up..."])
                    sh.push_packet(feed)
                log.info("user "+usr.username+" doesnt change the state")
            except users.UserError as e:
                log.debug(e.get_message())
                log.info("user "+usr.username+" doesnt change the state")  
                feed = Package(pack.FROM, [13, "User status error - some missunderstading happened"])
        elif choose == 6:#(User obj)
            usr = data[1]
            log.info("user %s wants to left work domain", usr.username)
            
            #flags
            log.info("changing flags...")
            try:
                usr.left_work_domain()
            except users.UserError as e:
                log.debug(e.get_message())
                log.info("user "+usr.username+" doesnt change the state")
        elif choose == 7:#(login, pass)
            log.info("someone wants to register")
            username = data[1]
            password = data[2]
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
        elif choose == 15:
            data = hyper.get_gaming_info()
            feed = Package(pack.FROM, [15, data])
            sh.push_packet(feed)
        elif choose == 16:
            usr = None
            for u in user_status:
                if u.user_id == pack.data[1]:
                    usr = u
                    break
            if usr != None:        
                data = hyper.get_work_info(usr.work_domain_name)
                feed = Package(pack.FROM, [16, data])
                sh.push_packet(feed)
        elif choose == 19:
            timeout_feed.append(pack.data[1])
        elif choose == 20:
            log.info("Slave has written: %s", pack.data[1])
        elif choose == 21:
            hyper.last_nv_count = [pack.FROM, pack.data[1]]
        elif choose == 23:#send pair code to the gaming domain
            dom_ip = pack.data[1]
            code = pack.data[2]
            log.info("pairing %s with code %s", dom_ip, code)
            pair_gaming_domain(pack, dom_ip, code)
            
        else: pass

