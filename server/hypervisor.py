#! /usr/bin/env python3

import bisect
import libvirt
import shutil
import xml.etree.ElementTree as ET
import os
import logging
import time
import threading

from resources import Package

global sh

class DomainError(Exception):
    NOT_FOUND = 1
    IS_RUNNING = 2
    IS_NOT_RUNNING = 3
    IS_OCCUPIED = 4
    EMPTY_NOT_FOUND = 5
    STATUS_ALREADY_EXISTS = 6
    IS_BOOTING_UP = 7
    
    def __init__(self, message, gaming, code):
        self.__gaming = gaming
        self.__message = message
        self.__code = code
    
    def get_code(self):
        return self.__code
    
    def get_message(self):
        s = "DomainError : " + self.__message
        return s
    
    def is_gaming(self):
        return self.__gaming


class DomainStatus:    
    def __init__(self, name, ID, obj, gaming):
        self.name = name
        self.ID = ID
        self.ip = ""
        self.obj = obj
        self.using = False
        self.gaming = gaming
        if gaming:
            self.booting_up = True
        else:
            self.booting_up = False
            self.tunnel = False
        
        self.user = None
    
    def __repr__(self):
        s = self.name + "," + str(self.ID) + "\nusing: " + str(self.using) + "\nuser: " + str(self.user) +"\ngaming: " + str(self.gaming)+"\nbooting_up: "+str(self.booting_up)
        return s
    
    def __lt__ (self, other):
        return self.name < other.name

class Hypervisor:
    #default filepaths
    __vm_path = "~/VM/"
    __disks_path = "Disks/"
    __blank_disks = "Disks/blank/"
    __blank_work_disk_name = "win_work.qcow2"
    __new_work_domain_xml = "~/VM/blank_work_domain.xml"
    
    #lists of working domains status
    __gaming_domains_working = []
    __work_domains_working = []
    
    #list of threads which are shutting down domains or checks if they are booted up meanwhile
    __sure_sh_threads = []
    __gaming_startup_threads = []
        
    def __init__(self, shell, config):
        self.__log = logging.getLogger(__name__)
        self.__log.info('constructing Hypervisor object')
        
        self.reload_config(config)       
        
        self.__log.debug("Hypervisor configs:")
        self.__log.debug("vm_path: %s", Hypervisor.__vm_path)
        self.__log.debug("disks_path: %s", Hypervisor.__disks_path)
        self.__log.debug("blank_disks: %s", Hypervisor.__blank_disks)
        self.__log.debug("blank_work_disk_name: %s",  Hypervisor.__blank_work_disk_name)
        self.__log.debug("new_work_domain_xml: %s", Hypervisor.__new_work_domain_xml)
        
        #this flag says if there is critical error
        #main scrpt checks it and whether it is true, it shutting down all server
        self.__critical = False
        
        self.__log.info('making connection with QEMU driver...')
        self.__conn = self.__conn_hypervisor()
        
        self.__log.info('checking if there are already running domains...')
        self.__find_running()
        
        #to communicate with slave
        self.__shell = shell
        self.last_nv_count = []#(ip, count)
        
        self.__log.info('Hypervisor construction done')
    
    def reload_config(self, config):
        Hypervisor.__vm_path = config['vm_path']
        Hypervisor.__disks_path = config['disks_path']
        Hypervisor.__blank_disks = config['blank_disks']
        Hypervisor.__blank_work_disk_name = config['blank_work_disk_name']
        Hypervisor.__new_work_domain_xml = config["new_work_domain_xml"]        
    
    def __conn_hypervisor(self):
    #connects with driver
        try:
            conn = libvirt.open("qemu:///system")
            #conn = libvirt.open("test:///default")
            self.__log.info("connection with QEMU: OK")
            return conn
        except libvirt.libvirtError as e:
            self.__log.exception(e.get_error_message())
            self.__log.critical("Hypervisor cannot connect with QEMU driver - server cant work properly")
            self.__critical = True
            
    
    
    def __find_running(self):
    #finds working domains and mark them as working and not being used
        try:
            self.__log.debug('grabbing working IDs')
            workingIDs = self.__conn.listDomainsID()
            self.__log.debug('checking every...')
            for ID in workingIDs:
                try:
                    self.__log.debug('domain id: %s', ID)
                    dom =  self.__conn.lookupByID(ID)
                    name = dom.name()
                    if name[0] == "g":
                        gaming = True
                    else: 
                        gaming = False
                    status = DomainStatus(name, ID, dom, gaming)
                    self.__log.info('found status: %s', status.name)
                    self.__log.debug(str(status))
                    self.__add_to_working_statuses(status)
                    
                    #checking if g_domain is still booting up
                    if status.gaming:
                        st = threading.Thread(target=self.__gaming_startup, name="g_start_"+status.name, args=(name, "g_start_"+status.name))
                        st.start()
                        Hypervisor.__gaming_startup_threads.append(st)
                except libvirt.libvirtError as e:
                    self.__log.exception(e.get_error_message())
        except libvirt.libvirtError as e:
            self.__log.exception(e.get_error_message())
    
      
    def __add_to_working_statuses(self, status):
    #adds status to list of working ones
        self.__log.debug('adding status\n' + str(status) + '\nto working ones')
        if status.gaming:
            bisect.insort_right(Hypervisor.__gaming_domains_working, status)
        else:
            bisect.insort_right(Hypervisor.__work_domains_working, status)
        self.__log.info("domain status of "+status.name+" added")
    
    def __find_mendacity(self, name):
    #checks if status object has wrong information about real state of domain (or does have nothing)
        self.__log.info('checking mendacity of '+ name)
        if name[0] == "g":
            try:
                self.find_gaming_status(name)
                status_found = True
            except DomainError as e:
                status_found = False
            finally:
                domain_working = self.check_running(name)
                mendacity = status_found ^ domain_working
                self.__log.info('is mendacity... %s', mendacity)
        else:
            try:
                self.find_work_status(name)
                status_found = True
            except DomainError as e:
                status_found = False
            finally:
                domain_working = self.check_running(name)
                mendacity = status_found ^ domain_working
                self.__log.info('is mendacity... %s', mendacity)
        
        self.__log.debug("values: %s, %s, %s" ,mendacity, status_found, domain_working)
        return mendacity, status_found, domain_working
    
    def __sure_shutdown(self, name, ID):
        log = logging.getLogger(ID)
        retry = 1
        while self.check_running(name):
            try:
                if retry < 10: 
                    log.info("domain %s is running, but has to be down - sending shutdown flag - attempt %s", name, retry)
                else:
                    log.warning("domain %s is still running, but has to be down - It takes more than 10 tries, should be inspected - attempt %s", name, retry)
                dom = self.__conn.lookupByName(name)
                dom.shutdown()
                retry+=1
            except libvirt.libvirtError as e:
                log.exception(e.get_error_message())
                break
            else: 
                log.info("waiting 30 seconds...")
                time.sleep(30)
                       
        
        self.__log.info("domain %s is down for sure", name)
        #removing a thread from list
        Hypervisor.__sure_sh_threads.remove(threading.currentThread())

    def __gaming_startup(self, name, ID):
        log = logging.getLogger(ID)
        log.info("starting gaming startup thread")
        
        #chcking if QEMU Guest agent is up
        dom = self.__conn.lookupByName(name)
        error = True
        ip = ""
        while error:
            try:
                ifaces = dom.interfaceAddresses(libvirt.VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_AGENT)
                
                log.info(ifaces)
                for i_name, val in ifaces.items():
                    if i_name.find("Ethernet 2") >= 0:
                        for ipaddr in val['addrs']:
                            if ipaddr['type'] == libvirt.VIR_IP_ADDR_TYPE_IPV4:
                                ip = ipaddr['addr']
                
                log.debug("found addres: %s", ip)
            except libvirt.libvirtError as e:
                error = True
                #waiting 2 sec for another request
                time.sleep(2)                
            else:
                error = False
                log.info("OS of domain %s has booted up", name)
        
        #then chceck if slave is up
        error = True
        request = Package(ip, [21])
        self.__shell.push_packet(request)
        time.sleep(1)
        while error:
            if len(self.last_nv_count) > 0:
                if self.last_nv_count[0] == ip and self.last_nv_count[1] >= 3:
                    error = False
                    self.last_nv_count = []
                    log.info("Domain %s is fully operational", name)
            
            request = Package(ip, [21])
            self.__shell.push_packet(request)   
            
            time.sleep(10)
            
        #find status IN list!!!
        for i in range(len(Hypervisor.__gaming_domains_working)):
            if Hypervisor.__gaming_domains_working[i].name == name:
                Hypervisor.__gaming_domains_working[i].booting_up = False
                Hypervisor.__gaming_domains_working[i].ip = ip
        
        #erasing from working startup threads
        Hypervisor.__gaming_startup_threads.remove(threading.currentThread())
                    
                
    
    def create_work_domain(self, username):
        '''USE ONLY WITH REGISTRATION
        creats a new work domain'''    
        #paths
        self.__log.info('start of creating domain win-work-%s', username)
        work_disk_name = Hypervisor.__blank_work_disk_name[:-6] + "_" + username + Hypervisor.__blank_work_disk_name[-6:]
        source_path = Hypervisor.__vm_path + Hypervisor.__blank_disks + Hypervisor.__blank_work_disk_name
        destination_path = Hypervisor.__vm_path + Hypervisor.__disks_path + work_disk_name
        
        self.__log.info("Creating backing file of %s in %s", source_path, destination_path)
        os.system("qemu-img create -f qcow2 -b %s %s" % (source_path, destination_path))
        self.__log.info ("Successfully created")
        os.chmod(destination_path, 0o600)
        
        self.__log.info('changing xml data...')
        tree = ET.parse(Hypervisor.__new_work_domain_xml)
        root = tree.getroot()
        self.__log.debug('changing domain name')
        name = root.find("name")
        name.text = name.text + "-" + username
        
        self.__log.debug("changing disk path")
        sources = root.findall(".//disk/source")
        for node in sources:
            if node.attrib["file"] == source_path:
                node.set("file", destination_path)
        
        domain_xml = ET.tostring(root)
        #print (domain_xml)
        try:
            self.__conn.defineXML(domain_xml.decode())
        except libvirt.libvirtError as e:
            self.__log.exception(e.get_error_message)
        else:
            self.__log.info('domain win-work-%s succefully defined', username)
            
    
    
    def check_running(self, name):
        '''checks if gave domain is not down'''
        try:
            self.__log.info('checking if domain %s is running, into the driver', name)
            dom = self.__conn.lookupByName(name)
            ID = dom.ID()
            if ID == -1: return False
            return True
        except libvirt.libvirtError as e:
            self.__log.exception(e.get_error_message())
            return False
        
      
    def find_domains_names(self, names):
        '''find domains in defined ones and return virDomain objects'''
        objects = []
        self.__log.info('looking for virDomain objects into the driver...')
        for dom_name in names:
            try:
                dom = self.__conn.lookupByName(dom_name)
                objects.append(dom)
                self.__log.info("found domain: %s", dom_name)
            except libvirt.libvirtError as e:
                self.__log.exception(e.get_error_message())
                #inform about lack...    
        return objects
    
    
    def find_gaming_domain_down(self, max_gaming, user_count):
        '''finds gaming domain which is shutted down'''
        self.__log.info('checking amount of working gaming domains...')
        if user_count <= len(Hypervisor.__gaming_domains_working):
            raise DomainError("There is enough gaming domain working right now", True, DomainError.IS_RUNNING)
        self.__log.info('looking for domain which is not running...')
        i = 0
        for game in Hypervisor.__gaming_domains_working:
            self.__log.debug('checking %s', game.name)
            num = int(game.name[1:])
            if num is not i:
                self.__log.info("found g%s", i)
                return "g"+str(i)
            else:
                i+=1
        if i < max_gaming: 
            self.__log.info("found g%s", i)
            return "g"+str(i)#boot next domain
        raise DomainError("There is no gaming domain down",  True, DomainError.IS_RUNNING)
    
    
    def startup_name(self, name):
        '''startups domain of given name'''
        self.__log.info('procedure of startup of %s...', name)
        if name[0] == "g":
            gaming = True
        else:
            gaming = False
        
        #check cohesion
        mendacity, dom_status, dom_state = self.__find_mendacity(name)
        
        if dom_status == True and dom_state == True:
            raise DomainError(name+" is already running", gaming, DomainError.IS_RUNNING)
        
        if not mendacity:   
            try:
                self.__log.info('sending startup flag to the driver')
                dom = self.__conn.lookupByName(name)
                dom.create()
                
                #adding domains to working ones
                status = DomainStatus(name, dom.ID(), dom, gaming)
                self.__add_to_working_statuses(status)
                
                if gaming:
                    st = threading.Thread(target=self.__gaming_startup, name="g_start_"+status.name, args=(name, "g_start_"+status.name))
                    st.start()
                    Hypervisor.__gaming_startup_threads.append(st)
                else:
                    self.__log.info("domain %s started", name)
                
            except libvirt.libvirtError as e:
                self.__log.exception(e.get_error_message())
        else:
            if dom_status == True and dom_state == False:#starting domain without adding status
                self.__log.info('sending startup flag to the driver')
                dom = self.__conn.lookupByName(name)
                dom.create()
                if gaming:
                    st = threading.Thread(target=self.__gaming_startup, name="g_start_"+status.name, args=(name, "g_start_"+status.name))
                    st.start()
                    Hypervisor.__gaming_startup_threads.append(st)
                else:
                    self.__log.info("domain %s started", name)
            else:#only adding status
                virObj = self.__conn.lookupByName(name)
                status = DomainStatus(name, virObj.ID(), virObj, gaming)
                if gaming:
                    st = threading.Thread(target=self.__gaming_startup, name="g_start_"+status.name, args=(name, "g_start_"+status.name))
                    st.start()
                    Hypervisor.__gaming_startup_threads.append(st)

                self.__add_to_working_statuses(status)
        self.__log.info('...procedure of startup of %s done', name)
        
    
    def shutdown_name(self, name, force=False):
        '''shutdown domain of given name'''
        self.__log.info('procedure of shutdown of %s...', name)
        status_obj = None
        
        #checking if this domains is already running
        self.__log.info('checking if domain is already running')
        if name[0] == "g":
            gaming = True
            status_obj = self.find_gaming_status(name)
        else:
            gaming = False
            status_obj = self.find_work_status(name)

        if status_obj.using == False:
            self.__log.info('running async shutdown function')
            sh = threading.Thread(target=self.__sure_shutdown, name="sure_sh_"+name, args=(name,"sure_sh_"+name))
            sh.start()
            #adding thread to list
            Hypervisor.__sure_sh_threads.append(sh)
            
            self.__log.info('erasing domain status from working ones')
            #erasing it from working ones
            if status_obj.gaming:
                Hypervisor.__gaming_domains_working.remove(status_obj)
            else:
                Hypervisor.__work_domains_working.remove(status_obj)
        elif force:
            self.__log.info("forcing shutdown of %s", name)
            self.__log.info('running async shutdown function')
            sh = threading.Thread(target=self.__sure_shutdown, name="sure_sh_"+name, args=(name,"sure_sh_"+name))
            sh.start()
            #adding thread to list
            Hypervisor.__sure_sh_threads.append(sh)
            
            self.__log.info('erasing domain status from working ones')
            #erasing it from working ones
            if status_obj.gaming:
                Hypervisor.__gaming_domains_working.remove(status_obj)
            else:
                Hypervisor.__work_domains_working.remove(status_obj)            
        else:
            raise DomainError(status_obj.user+" is using "+ status_obj.name +" right now", gaming, DomainError.IS_OCCUPIED)
        self.__log.info('...procedure of shutdown of %s done', name)
        
    def find_empty_gaming_status (self):
        self.__log.info('looking for empty gaming status')
        for i in range(len(Hypervisor.__gaming_domains_working)):
            if Hypervisor.__gaming_domains_working[i].using == False and Hypervisor.__gaming_domains_working[i].booting_up == False:
                self.__log.info('found empty and ready: %s', Hypervisor.__gaming_domains_working[i].name)
                return Hypervisor.__gaming_domains_working[i]
        raise DomainError("No empty ready gaming domain", True, DomainError.EMPTY_NOT_FOUND)
    
    def find_work_status (self, name):
        self.__log.info('looking for work status: %s', name)
        for i in range(len(Hypervisor.__work_domains_working)):
            if Hypervisor.__work_domains_working[i].name == name:
                self.__log.info('status found')
                return Hypervisor.__work_domains_working[i]
        raise DomainError(name+" status: is not running", False, DomainError.IS_NOT_RUNNING)
    
    def find_gaming_status (self, name):
        self.__log.info('looking for gaming status: %s', name)
        for i in range(len(Hypervisor.__gaming_domains_working)):
            if Hypervisor.__gaming_domains_working[i].name == name:
                self.__log.info('status found')
                return Hypervisor.__gaming_domains_working[i]
        raise DomainError(name+" status: is not running", True, DomainError.IS_NOT_RUNNING)        
    
    def list_status(self):
        print ("Gaming domains:")
        for status in Hypervisor.__gaming_domains_working:
            print (status)
        print ("Work domains:")
        for status in Hypervisor.__work_domains_working:
            print (status)
    
    def get_gaming_info(self):
        data = []
        for dom in self.__gaming_domains_working:
            data.append(dom.name)
            if dom.using == True:
                status = "USING"
                user = dom.user
            elif dom.booting_up == True:
                status = "BOOTING UP"
                user = "NOBODY"
            else:
                status = "READY"
                user = "NOBODY"
            data.append(status)
            data.append(user)
        
        return data
    
    def get_work_info(self, name):
        data = []
        
        for d in self.__work_domains_working:
            if d.name == name:
                data.append(d.name)
            if d.using == True:
                status = "USING"
            elif d.booting_up == True:
                status = "BOOTING UP"
            else:
                status = "READY"
            data.append(status)
            data.append(d.tunnel)
            
        
        return data
    
    def is_critical(self):
        return self.__critical
    
    def close(self):
        self.__log.info("preparing Hypervisor object for shutdown")
        
        #checking if some domains are still running
        #doing all shutdown without flags and removing from lists, because this time server is stopping its work
        if len(Hypervisor.__work_domains_working):
            self.__log.warning("There are still %s work domains running", len (Hypervisor.__work_domains_working))
            for status in Hypervisor.__work_domains_working:
                if status.using:
                    choose = str(input(status.name+" is using right now - do you want to shutdown it anyway?(y/n)"))
                    if choose.upper() == 'Y':
                        self.shutdown_name(status.name, True)
                else:
                    self.shutdown_name(status.name)
            self.__log.info("All work domains are set to down")
        
        if len(Hypervisor.__gaming_domains_working):
            self.__log.warning("There are still %s gaming domains running", len (Hypervisor.__gaming_domains_working))
            for status in Hypervisor.__gaming_domains_working:
                if status.using:
                    choose = str(input(status.name+" is using right now - do you want to shutdown it anyway?(y/n)"))
                    if choose.upper() == 'Y':
                        self.shutdown_name(status.name, True)
                else:
                    self.shutdown_name(status.name)        
            self.__log.info("All gaming domains are set to down")
            
        #chcecking if some domains are still being shuted down
        if len(Hypervisor.__sure_sh_threads):
            self.__log.warning("There are %s sure_sh threads running in the background - waiting for end of work", len(Hypervisor.__sure_sh_threads))
            while len (Hypervisor.__sure_sh_threads):
                for th in Hypervisor.__sure_sh_threads:
                    try:
                        self.__log.info("joining %s...", th.name)
                        th.join()
                    except Exception as e:
                        #Everything can happen with asynchronous functions
                        self.__log.exception(e.args)
            self.__log.info("All threads ended their work")
        try:
            self.__log.info('closing connection with QEMU')
            self.__conn.close()
        except libvirt.libvirtError as e:
            self.__log.exception (e.get_error_message())
        self.__log.info("Hypervisor object ready for shutdown")
