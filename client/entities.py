#! /usr/bin/env python3

import curses
import logging
import logging.config
import threading

from systems_components import *

logging.config.fileConfig("logs/log.conf")

class Entity:
    def __init__(self, py, px, dy, dx, asc, name):
        self._log = logging.getLogger(name)
        self._log.info("Initializing entity...")
        #None means that this entity is below the root window
        self._asc = asc
        self._desc = []
        self._window = None
        self.position = console_point(py, px)
        self.dimentions = console_point(dy, dx)
        self._components_list = []
        
        self.name = name
        
        self._log.debug("position: %s", self.position)
        self._log.debug("dimentions: %s", self.dimentions)
        
        if self._asc != None:
            self._asc.add_descendant(self)
        
        Box_system.add_entity(self)
        self._registered = True
    
    def __lt__(self, other):
        return self.name < other.name
    
    def __gt__(self, other):
        return self.name > other.name
    
    def __cmp__(self, other):
        return self.name == other.name
        
    def get_win(self):
        return self._window
    
    def is_registered(self):
        return self._registered
    
    def change_position(self, point):
        self.position = point
        self._create_window()
        
        for i in range(len(self._desc)):
            self._desc[i].change_position(self._desc[i].position)        
        
        #reinitialize components
        for i in range(len(self._components_list)):
            self._components_list[i].reinitialize()         
    
    def get_ascendant(self):
        return self._asc
    
    def add_descendant(self, desc):
        self._desc.append(desc)
    
    def del_descendant(self, desc):
        self._desc.remove(desc)
    
    def _create_window(self):
        self._log.info("creating window")
        if self._asc == None:
            self._window = Box_system.get_root_window().derwin(self.dimentions.y, self.dimentions.x, self.position.y, self.position.x)
        else:
            self._window = self._asc.get_win().derwin(self.dimentions.y, self.dimentions.x, self.position.y, self.position.x)
    
    def get_absolute_position(self):
        if self._window != None:
            y, x = self._window.getbegyx()
            return console_point(y, x)
    
    def add_component(self, comp):
        self._components_list.append(comp)
    
    def finish(self):
        self._log.info("finishing work of entity")
        self._registered = False
        if self._asc != None: 
            self._asc.del_descendant(self)
        while len(self._components_list):
            self._components_list[0].unregister()
            del self._components_list[0]

class Text_box(Entity):
    """
    This object just shows text inside\n
    kwargs:\n
        content - content to show (list/string, d="txtBox")\n
        color - color of content (color_num, d=0)\n
        fit - window is fitted to content (bool, d=False)\n
        border - if border is set (bool, d=False)\n
        offx - content offset on x axis (int, d=0)\n
        offy - content offset on y axis (int, d=0)\n
        border_ch - characters used to create border (tuple - size (8), d-\n
                      (curses.ACS_SBSB,\n
                       curses.ACS_SBSB,\n
                       curses.ACS_BSBS,\n
                       curses.ACS_BSBS,\n
                       curses.ACS_BSSB,\n
                       curses.ACS_BBSS,\n
                       curses.ACS_SSBB,\n
                       curses.ACS_SBBS)\n
    """    
    def __init__(self,name, asc, py, px, dy=0, dx=0, **kw):
        
        #text_component variables
        content = kw.get("content", "txtBox")
        fit = kw.get("fit", False)
        border = kw.get("border", False)
        ox = kw.get("offx", 0)
        oy = kw.get("offy", 0)
        border_ch = kw.get("border_ch", (curses.ACS_SBSB, curses.ACS_SBSB, curses.ACS_BSBS, curses.ACS_BSBS, curses.ACS_BSSB, curses.ACS_BBSS, curses.ACS_SSBB, curses.ACS_SBBS))
        color = kw.get("color", Colors.pair("default"))
        
        Entity.__init__(self, py, px, dy, dx, asc, name)

        self._log.info("adding components...")
        self.text_component = Text_component(self, content, color, oy, ox, border, border_ch, fit)       
        self._create_window()
        
        self._log.info("initialization done")
    
    def set_content(self, content):
        self.text_component.set_content(content)

class Button_box(Entity):
    """
    This object shows text and handles clicks into it like button\n
    kwargs:\n
        content - content to show (list/string, d="txtBox")\n
        outline - amount of character to make collider bigger than window (int, d=0)\n
        is_start - it says if this entity is first to mark by KMS (bool, d=False)\n
        color1 - color of content without click (color_num, d=0)\n
        color2 - coclor to show during click (color_num, d=1)\n
        fit - window is fitted to content (bool, d=False)\n
        border - if border is set (bool, d=False)\n
        offx - content offset on x axis (int, d=0)\n
        offy - content offset on y axis (int, d=0)\n
        border_ch - characters used to create border (tuple - size (8), d-\n
                      (curses.ACS_SBSB,\n
                       curses.ACS_SBSB,\n
                       curses.ACS_BSBS,\n
                       curses.ACS_BSBS,\n
                       curses.ACS_BSSB,\n
                       curses.ACS_BBSS,\n
                       curses.ACS_SSBB,\n
                       curses.ACS_SBBS)\n
    
    """    
    def __init__(self, name, asc, py, px, dy=0, dx=0, **kw):
        #text_component variables
        fit = kw.get("fit", False)
        border = kw.get("border", False)
        ox = kw.get("offx", 0)
        oy = kw.get("offy", 0)
        border_ch = kw.get("border_ch", (curses.ACS_SBSB, curses.ACS_SBSB, curses.ACS_BSBS, curses.ACS_BSBS, curses.ACS_BSSB, curses.ACS_BBSS, curses.ACS_SSBB, curses.ACS_SBBS))        
        content = kw.get("content", "btnBox")
        
        #collider variables
        coll_outline = kw.get("outline", 0)
        start = kw.get("is_start", False)
        
        #button variables
        self.__color1 = kw.get("color1", Colors.pair("defaul"))
        self.__color2 = kw.get("color2", Colors.pair("reverse"))
        self.__clicked = False
        self.__locked = False
        
        self.__click_func = None
        self.__click_func_args = None
        self.__click_th = None
        self.__unclick_func = None
        self.__unclick_func_args = None
        self.__unclick_th = None
        
        Entity.__init__(self, py, px, dy, dx, asc, name)
        
        self._log.info("adding components...")
        self.text_component = Text_component(self, content, self.__color1, oy, ox, border, border_ch, fit)
        self._create_window()
        
        #collider component has to have a window object
        self.collider_component = Collider_component(self, self.dimentions, coll_outline)
        self.key_man_component = Keyboard_manipulation_component(self, start)
        self._log.info("initialization done")
    
    def click(self):
        if self.__clicked == False and self.__locked == False:
            self._log.info("click function")
            self.text_component.color = self.__color2
            self.__clicked = True
            Box_system.refresh()
            
            if self.__click_func != None:
                self.__click_th = threading.Thread(target = self.__click_func, name=self.name+"-click", args=(*self.__click_func_args,))
                self.__click_th.start()
                
    def unclick(self):
        if self.__clicked == True and self.__locked == False:
            self._log.info("unclick function")
            self.text_component.color = self.__color1
            self.__clicked = False
            Box_system.refresh()
            
            if self.__unclick_func != None:
                self.__unclick_th = threading.Thread(target=self.__unclick_func, name=self.name+"-unclick", args=(*self.__unclick_func_args,))
                self.__unclick_th.start()
                
    def set_click(self, func, *args):
        self._log.debug("setting click_function %s - %s", func, args)
        self.__click_func = func
        self.__click_func_args = args
    
    def set_unclick(self, func, *args):
        self._log.debug("setting unclick_function %s - %s", func, args)
        self.__unclick_func = func
        self.__unclick_func_args = args
    
    def block_click(self):
        self.__locked = True
    
    def unblock_click(self):
        self.__locked = False

class Input_box(Entity):
    """
    This object is interactive input box. Can be also a password input:\n
        outline - amount of character to make collider bigger than window (int, d=0)\n
        is_start - it says if this entity is first to mark by KMS (bool, d=False)\n
        passwd - flag which says if this Input Box will be a password type (bool, d=False)
    """       
    def __init__(self, name, asc, py, px, dy, dx, **kw):
        #collider variables
        coll_outline = kw.get("outline", 0)
        start = kw.get("is_start", False)
        
        #input variables
        passwd = kw.get("passwd", False)
        
        Entity.__init__(self, py, px, dy, dx, asc, name)
        
        self._create_window()
        
        self._log.info("adding components...")
        self.input_component = Input_component(self, passwd)
        self.collider_component = Collider_component(self, self.dimentions, coll_outline)
        self.text_component = Text_component(self, "", Colors.pair("default"), 0, 0, False, (curses.ACS_SBSB, curses.ACS_SBSB, curses.ACS_BSBS, curses.ACS_BSBS, curses.ACS_BSSB, curses.ACS_BBSS, curses.ACS_SSBB, curses.ACS_SBBS), False)
        self.key_man_component = Keyboard_manipulation_component(self, start)
        
        self._log.info("initialization done")
    
    def click(self):
        self._log.info("click_function")
        self.input_component.get_input()
      
        if self.input_component.is_pass():
            self.text_component.set_content(self.input_component.fake_data)
        else:
            self.text_component.set_content(self.input_component.get_last_input())
            
        self._log.debug("end of click function")
        
    def unclick(self):
        pass