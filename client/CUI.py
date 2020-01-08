#! /usr/bin/env python3

import curses
from curses import wrapper
import curses.textpad
import logging.config
import logging
import time
import threading
import sys

import shell
import users
from resources import Package

from entities import *
from systems_components import Box_system
import moonlight_functions

logging.config.fileConfig("logs/log.conf", disable_existing_loggers=False)
log = logging.getLogger(__name__)

def login_window():
    global error_box
    global prompt_box
    
    #click functions
    def exit():
        curses.ungetch(1)
        shutdown()
    
    def login():
        global error_occur
        global user_id
        global username
        
        btnLogin.block_click()
        
        timeout = 30 #seconds
        
        data = Box_system.get_input_data(inputLogin, inputPass)
        txtError.set_content("")
        usr= data["inputLogin"]
        password = data["inputPass"]        
        
        if usr == "" or password == "":
            txtError.text_component.set_content("username and password is empty - do something with it!")
            
        else:    
            txtPrompt.text_component.set_content("logging in...")
            Box_system.refresh()
        
            pack = Package(SRV, [1, usr, password])
            sh.push_packet(pack)
            
            wait_time = time.time() + timeout
            
            log.debug("user_id: %s", user_id)
            log.debug("error_occur: %s", error_occur)
            
            while time.time() < wait_time and user_id == None and error_occur == False:
                time.sleep(0.1)#making a processor alive
                if Box_system.is_running == False:
                    return
            
            log.debug("user_id: %s", user_id)
            log.debug("error_occur: %s", error_occur)            
            
            if error_occur:
                error_occur = False
                txtPrompt.text_component.set_content("")
                btnLogin.unblock_click()
                Box_system.refresh()
            elif time.time() >= wait_time:
                txtError.text_component.set_content("login timed out")
                txtPrompt.text_component.set_content("")
                btnLogin.unblock_click()
                Box_system.refresh()
            else:
                username = usr
                #getting info from server
                sh.push_packet(Package(SRV, [18]))
                
                btnLogin.unblock_click()
                Box_system.refresh()                
                
                #experiment to stop artifacts on change
                time.sleep(0.5)
                Box_system.set_window_content("status_screen")
                 
        
    
    f = open("startup_text.txt")
    logo = f.read()
    f.close()    
    
    #definition of entities
    container = Text_box("container", None,
                        0, 0,
                        content=logo,
                        fit=True, border=True)
    
    btnLogin = Button_box("btnLogin", container,
                          21, 52,
                          content=" LOGIN ",
                          border=True, fit=True)
    btnLogin.set_click(login)
    
    btnExit = Button_box("btnExit", None,
                         0, 0,
                         content=" EXIT ",
                         border=True, fit=True)
    btnExit.set_click(exit)
    
    btnReg = Button_box("btnReg", container,
                        21, 2,
                        content=" REGISTER ",
                        border=True, fit=True)
    
    inputLogin = Input_box("inputLogin", container,
                           15, 18,
                           1, 29,
                           outline=1,
                           is_start=True)
    inputPass = Input_box("inputPass", container,
                          18, 18,
                          1, 29,
                          outline=1,
                          passwd=True)
    
    
    
    
    #moving entities around
    size = Box_system.get_win_size()
    container.change_position(console_point(int((size.y-container.dimentions.y) / 2), int((size.x-container.dimentions.x) / 2)))
    btnExit.change_position(console_point(0, size.x - btnExit.dimentions.x))
    
    txtError = Text_box("txtError", None,
                        container.position.y + container.dimentions.y + 1, container.position.x,
                        2, container.dimentions.x,
                        content="",
                        color = Colors.pair("error"))
    error_box = txtError
    
    txtPrompt = Text_box("txtPrompt", container,
                         21, 15,
                         2, 36,
                         content="")
    prompt_box = txtPrompt
    
    
    #definition of neighbours
    btnLogin.key_man_component.set_neighbours(inputPass, None, None, btnReg)
    btnExit.key_man_component.set_neighbours(None, None, inputLogin, inputLogin)
    btnReg.key_man_component.set_neighbours(inputPass, btnLogin, btnLogin, None)
    inputLogin.key_man_component.set_neighbours(btnExit, btnExit, inputPass, None)
    inputPass.key_man_component.set_neighbours(inputLogin, btnLogin, btnReg, btnReg)

def status_window():
    global error_box
    global prompt_box
    global g_domain_info
    
    #click_functions
    def exit():
        curses.ungetch(1)
        shutdown()
    
    def logout():
        global user_id
        global username
        
        if user_id != None:
            pack = Package(SRV, [2, user_id])
            sh.push_packet(pack)
            
            user_id = None
            username = None
            
        Box_system.set_window_content("login_screen")
    
    def use_gaming_domain():
        global user_id
        global error_occur
        
        pack = Package (SRV, [3, user_id])
        sh.push_packet(pack)
        
        if error_occur:
            error_occur = False
            return
        
        Box_system.set_window_content("game_choose_window")  
        
    
    w_status = ""
    with open("work_domain_status.txt") as f:
        w_status = f.read()
    
    header = Text_box("header", None, 0, 0, 5, Box_system.get_win_size().x, content="")
    txtWelcome = Text_box("txtWelcome", header,
                          0, 3,
                          content=["\__ WELCOME "+username.upper()+" __/"],
                          #content="WELCOME",
                          fit=True, border=False)
    
    txtClockFace = Text_box("txtClockFace", header,
                        0, 0,
                        content=["-------------"," \_       _/","   -------"], 
                        fit=True)
    
    txtClockData = Text_box("txtClockData", txtClockFace,
                            1, 4,
                            fit=True,
                            content="HH:MM")
    
    btnExit = Button_box("btnExit", header,
                         0, 0,
                         fit=True, border=True,
                         content=" EXIT ")
    btnExit.set_click(exit)
    
    btnLogout = Button_box("btnLogout", header,
                           0, 0,
                           fit=True, border=True,
                           content=" LOGOUT ")
    btnLogout.set_click(logout)
    
    btnSettings = Button_box("btnSettings", header,
                             0, 0,
                             fit=True, border=True,
                             content=" SETTINGS ")
    
    txtError = Text_box("txtError", header,
                        2, 3,
                        2, int(Box_system.get_win_size().x/2)-4,
                        content="",
                        color = Colors.pair("error"))
    
    domains = Text_box("domains", None, 6, 0,
                       int(Box_system.get_win_size().y*0.7), Box_system.get_win_size().x,
                       content="")
    
    g_domains = Text_box("g_domains", domains, 0, 0,
                         domains.dimentions.y-2, int(domains.dimentions.x/2)-1,
                         border=True, content="",
                         border_ch=(curses.ACS_SBSB,
                                    curses.ACS_SBSB,
                                    curses.ACS_BSBS,
                                    curses.ACS_BSBS,
                                    curses.ACS_BSSB,
                                    curses.ACS_BSSS, 
                                    curses.ACS_SSBB,
                                    curses.ACS_SSBS))
    
    g_head = Text_box("g_head", g_domains, 1, 0,
                      fit=True,
                      content="GAMING DOMAINS")
    
    g_row_tags = Text_box("g_row_tags", g_domains,
                         4, 3,
                         fit=True,
                         content=" NUM   NAME       STATUS        USER")
    
    g_rows_data = Text_box("g_rows_data", g_domains,
                           6, 5,
                           g_domains.dimentions.y-7, g_domains.dimentions.x - 7,
                           content="1. ...")
    g_domain_box = g_rows_data
    
    w_domain = Text_box("w_domain", domains, 0, int(domains.dimentions.x/2),
                        domains.dimentions.y-2, round(domains.dimentions.x/2)-2,
                        border=True, content="")
    
    w_head = Text_box("w_head", w_domain,
                         0, 0,
                         fit=True, content = "YOUR WORK DOMAIN")
    
    w_status = Text_box("w_status", w_domain,
                        4, 6,
                        w_domain.dimentions.y - 5, w_domain.dimentions.x - 7,
                        content = w_status)
    
    w_domain_name = Text_box("w_domain_name", w_status,
                             0, 14,
                             1, w_status.dimentions.x - 15,
                             content="N/A")
    
    w_domain_status = Text_box("w_domain_status", w_status,
                             2, 14,
                             1, w_status.dimentions.x - 15,
                             content="N/A") 
    
    w_domain_tunnel = Text_box("w_domain_tunnel", w_status,
                             4, 14,
                             1, w_status.dimentions.x - 15,
                             content="Y/N")
    
    btnGDomain = Button_box("btnGDomain", None,
                            0, 0,
                            fit=True, border=True,
                            content=" USE GAMING DOMAIN ",
                            is_start=True)
    btnGDomain.set_click(use_gaming_domain)
    
    btnWDomain = Button_box("btnWDomain", None,
                            0, 0,
                            fit=True, border=True,
                            content=" USE WORK DOMAIN ")
    
    error_box = txtError
    
    
    #moving entities around
    txtClockFace.change_position(console_point(0, int((Box_system.get_win_size().x - txtClockFace.dimentions.x) / 2) + 1))    
    
    btnExit.change_position(console_point(1, Box_system.get_win_size().x - btnExit.dimentions.x ))
    btnLogout.change_position(console_point(1, btnExit.position.x - 11))
    btnSettings.change_position(console_point(1, btnLogout.position.x - 13))
    
    g_head.change_position(console_point(1, int((g_domains.dimentions.x - g_head.dimentions.x) / 2)))
    w_head.change_position(console_point(1, int((w_domain.dimentions.x - w_head.dimentions.x) / 2)))
    
    btnGDomain.change_position(console_point(domains.dimentions.y + 6, int((Box_system.get_win_size().x - btnGDomain.dimentions.x)/4)))
    btnWDomain.change_position(console_point(domains.dimentions.y + 6, int((Box_system.get_win_size().x - btnWDomain.dimentions.x)*3/4)))    
    
    
    #setting neighbours
    btnSettings.key_man_component.set_neighbours(btnLogout, btnLogout, btnWDomain, btnWDomain)
    btnLogout.key_man_component.set_neighbours(btnExit, btnExit, btnSettings, btnSettings)
    btnExit.key_man_component.set_neighbours(None, None, btnLogout, btnLogout)
    btnGDomain.key_man_component.set_neighbours(btnWDomain, btnWDomain, None, None)
    btnWDomain.key_man_component.set_neighbours(btnSettings, btnSettings, btnGDomain, btnGDomain)
    
    def data_update_thread():
        log = logging.getLogger("dataUpdate")
        counter = 0
        while Box_system.get_current_content() == "status_screen" and Box_system.is_running():
            change = False
            #update clock data
            clock_data = time.strftime("%H:%M").split('\n')
            
            if txtClockData.text_component.get_content() != clock_data:
                txtClockData.set_content(clock_data)
                change = True
            
            
            if not counter%5:
                #pulling info
                if user_id != None:
                    pack = Package(SRV, [16, user_id])
                    sh.push_packet(pack)
                    pack = Package(SRV, [15])
                    sh.push_packet(pack)
                    
                #update work domain info    
                if w_domain_name.text_component.get_content() != w_name.strip("\n"):
                    w_domain_name.set_content(w_name)
                    change = True
                if w_domain_status.text_component.get_content() != w_status_str.strip("\n"):
                    w_domain_status.set_content(w_status_str)
                    change = True        
                if w_domain_tunnel.text_component.get_content() != w_tunnel_audio.strip("\n"):
                    w_domain_tunnel.set_content(w_tunnel_audio)
                    change = True 
                
                #update gaming domains info
                content = []
                for i in range( int(len(g_domain_info)/3)):
                    line = str(i+1)+".   "
                    line += g_domain_info[i*3]+"     "
                    line += g_domain_info[i*3+1]+"     "
                    line += g_domain_info[i*3+2]
                    content.append(line)
                
                if g_domain_box.text_component.get_content() != content:
                    g_domain_box.set_content(content)
                    change = True
            
            if change:
                Box_system.refresh()
            
            time.sleep(1)
            #counting seconds
            #not every update has to be done every second
            counter+=1
            if counter == 60:
                counter = 0
        
        log.info("closing Data Update thread on status_screen")
    
    #running useful threads
    dataUpdateTh = threading.Thread(target=data_update_thread, name="clockDataTh", daemon=True)
    dataUpdateTh.start()    
    

def game_choose_window():
    global error_box
    global prompt_box
    
    #click functions
    def return_status():
        try:
            leave_pack = Package(SRV, [4, user_id])
            sh.push_packet(leave_pack)
            using_gdomain_address = ""
            
            Box_system.set_window_content("status_screen")
        except Exception as e:
            log.exception(e.args)    
    
    def choose_game(name):
        moonlight_functions.stream_game(name, using_gdomain_address)
        return_status()

    def list_games():
        txtPrompt.set_content("Waiting for game list...")
        Box_system.refresh()

        game_list = moonlight_functions.list_available_games(using_gdomain_address)
        btn_list = []  # list of buttons with games

        # generating buttons with games' names
        if Box_system.get_current_content() == "game_choose_window":
            if game_list is not None:
                txtPrompt.set_content('')
                Box_system.refresh()

                position = console_point(5, 2)
                dimentions = console_point(1, 20)
                spacing = console_point(1, 1)
                border = console_point(2, 2)
                pointer = position

                for i in range(len(game_list)):
                    btn = Button_box("game" + str(i + 1), None, pointer.y, pointer.x, dimentions.y, dimentions.x,
                                     content=game_list[i],
                                     border=True)
                    btn.set_click(choose_game, (btn.text_component.get_content()[0]))
                    btn_list.append(btn)

                    if (pointer.x + border.x + dimentions.x + spacing.x) > maks.x and (
                            pointer.y + border.y + dimentions.y + spacing.y) > maks.y:
                        break
                    elif (pointer.x + border.x + dimentions.x + spacing.x) > maks.x:
                        pointer.x = position.x
                        pointer.y = pointer.y + dimentions.y + border.y + spacing.y
                    else:
                        pointer.x = pointer.x + dimentions.x + border.x + spacing.x

                # neighbours
                in_row = int((maks.x - position.x) / (dimentions.x + border.x + spacing.x))

                for i in range(len(btn_list)):
                    btn_list[i].key_man_component.set_neighbours(btn_list[(i - in_row) % len(btn_list)],
                                                         btn_list[(i + 1) % len(btn_list)],
                                                         btn_list[(i + in_row) % len(btn_list)],
                                                         btn_list[(i - in_row) % len(btn_list)])

                btn_list[0].key_man_component.set_neighbour(btnReturn, btn_list[0].key_man_component.UP_NEIGH)
                btnReturn.key_man_component.set_neighbours(btn_list[-1], None, btn_list[0], btn_list[0])
                return 0
            else:  # or say it failed
                txtError.set_content("There are game list error")
                return 1
    
    
    maks = Box_system.get_win_size()
    
    btnReturn = Button_box("btnReturn", None, 
                           1, maks.x - 17,
                           fit=True,
                           border=True,
                           content=" STATUS SCREEN ")
    btnReturn.set_click(return_status)
    
    txtError = Text_box("txtError", None,
                        1, 0,
                        2, int((maks.x-btnReturn.dimentions.x-2)/2),
                        content="", 
                        color=Colors.pair("error"))
    error_box = txtError
    
    txtPrompt = Text_box("txtPrompt", None,
                        1, int((maks.x-btnReturn.dimentions.x-2)/2)+1,
                        2, int((maks.x-btnReturn.dimentions.x-2)/2),
                        content="")
    prompt_box = txtPrompt

    # Begin of logic of the screen
    error = list_games()
    Box_system.refresh()

    # If there is error while listing, maybe we should pair
    if error:
        if not pair_with_domain(using_gdomain_address):
            list_games()
    Box_system.refresh()


    
def CUI():
    #initializing curses
    stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    curses.start_color()
    
    Box_system(stdscr)
    
    Colors.add_pair("error", Colors.color("red"), Colors.color("black"))
    
    Box_system.add_window_content("login_screen", login_window)
    Box_system.add_window_content("status_screen", status_window)
    Box_system.add_window_content("game_choose_window", game_choose_window)
    
    Box_system.set_window_content("login_screen")
    
    while Box_system.is_running():
        Box_system.wait_for_key()
    
    curses.nocbreak()
    stdscr.keypad(False)
    curses.echo()
    curses.endwin()
        

def shutdown():
    global running
    
    log.info("shutting down...")
    
    if user_id != None:
        pack = Package(SRV, [2, user_id])
        sh.push_packet(pack)
    
    #sending flags
    running = False
    if sh != None: sh.exit()
    curses.ungetch(1)
    
    #waiting to stop the Box_system
    log.debug("waiting for cui_th")
    cui_th.join()
    
    log.info("...shutdown done")


def pair_with_domain(dom_ip):
    code = moonlight_functions.randomize_code()
    output = []
    try:
        log.debug("starting thread to pair")
        # starting thread to send a pair request
        pair_req = threading.Thread(target=moonlight_functions.send_pair_request, name="pair_req",
                                    args=(dom_ip, output))
        pair_req.start()

        # waiting LESS THAN timeout for moonlight-embedded to find LOCAL errors
        time.sleep(0.5)
        log.debug("checking local errors - output: %s", output)
        if len(output) != 0:
            if output[0] == 'Failed to pair to server: Already paired\n':
                prompt_box.set_content(output[0])
            else:
                error_box.set_content(output[0])

                error_pack = Package(SRV, [4, user_id])
                sh.push_packet(error_pack)
                error_occur = True
                Box_system.refresh()
                return 1
            Box_system.refresh()
        else:
            # sending pair code to the server if local error doesnt occur
            code_pack = Package(SRV, [23, dom_ip, str(code)])
            sh.push_packet(code_pack)

            while len(output) == 0:
                time.sleep(0.1)

            if output[0] != "PAIRED":
                error_box.set_content(output[0])

                error_pack = Package(SRV, [4, user_id])
                sh.push_packet(error_pack)
                error_occur = True
                Box_system.refresh()
                return 1
    except:
        log.error("Error while pairing request - i dont know which (DEBUGING)")
        return 1

    return 0


# ==========
# == MAIN ==
# ==========

vers = "0.1"
min_srv_vers = 0.3

PORT = 57201
SRV = "10.0.10.92"
SRV_IP = (SRV, PORT)

#data from server
user_id = None
username = None
max_gaming_count = None

#w_domain data
w_name = "N/A"
w_status_str = "N/A"
w_tunnel_audio = "N/A"

#g_domain info
# k+0 - name
# k+1 - status
# k+2 - user
g_domain_info = []
using_gdomain_address = ""

#threads
stop_CUI = False
cui_th = None
sh = None

#flags
running = True
error_occur = False

#useful boxes
error_box = None
prompt_box = None

def main():
    global sh
    global cui_th
    global error_occur
    global user_id
    global max_gaming_count
    global w_name
    global w_status_str
    global w_tunnel_audio
    global g_domain_info
    global using_gdomain_address
    
    log.info("starting MoonlightMultisession client software - vers %s", vers)
    
    #starting communication shell
    sh = shell.Shell(SRV, PORT)
    
    #starting CUI in other thread
    cui_th = threading.Thread(target=CUI, name="CUI", args=())
    cui_th.start()
    
    #wait for shell to fully start
    time.sleep(0.1)
    
    #received data
    while running:
        #slowing down the cpu
        time.sleep(0.01)
        
        pack = sh.get_packet()
        # log.debug(pack)
        if pack != None:
            choose = pack.data[0]
            # login
            if choose == 1 and pack.errcode == 0:
                user_id = pack.data[1]
                max_gaming_count = pack.data[2]
                for i in range(max_gaming_count*3):
                    g_domain_info.append("N/A")
            if choose == 3:
                using_gdomain_address = pack.data[1];
            # error
            elif choose == 13:
                error_occur = True
                error_box.text_component.set_content(pack.data[1])
                Box_system.refresh()
            # prompt
            elif choose == 14:
                prompt_box.text_component.set_content(pack.data[1])
                Box_system.refresh()
            # g_domain info
            elif choose == 15:
                if max_gaming_count is not None:
                    g_domain_info = pack.data[1]
            # w_domain info
            elif choose == 16:
                data = pack.data[1]
                if len(data) > 0:
                    w_name = data[0]
                    w_status_str = data[1]
                    if data[2]:
                        w_tunnel_audio = 'TRUE'
                    else:
                        w_tunnel_audio = "FALSE"
            # timeout checking
            elif choose == 19 and user_id is not None:
                pack = Package(SRV, [19, user_id])
                sh.push_packet(pack)
                
                        
                
                
            


if __name__ == "__main__":
    main()
