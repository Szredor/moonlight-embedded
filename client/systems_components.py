#! /usr/bin/env python3

import curses
import curses.ascii
import logging
import logging.config
import bisect
import types


"""
Implementation of Entity-Component-System

Systems:
    - Text
    - Collider
    - Input
    - Keyboard_Manipulation
"""

logging.config.fileConfig("logs/log.conf")

class console_point:
    
    def __init__(self, y, x):
        self.y = y
        self.x = x
        
        self.cols = x
        self.rows = y

    def __repr__(self):
        return "("+str(self.y)+","+str(self.x)+")"
    
    def __eq__(self, other):
        if self.y == other.y and self.x == other.x:
            return True
        return False
    
    def __add__(self, other):
        return console_point(self.y + other.y - 1, self.x + other.x - 1)

class Colors:
    __colors = dict()
    __color_pairs = dict()
    
    __colors_num = 0
    __pairs_num = 0
    
    def __init__(self):
        Colors.__log = logging.getLogger("Colors")
        Colors.__log.info("initializing colors")
        
        curses.use_default_colors()
        
        Colors.__colors["black"] = curses.COLOR_BLACK
        Colors.__colors["white"] = curses.COLOR_WHITE
        Colors.__colors["red"] = curses.COLOR_RED
        Colors.__colors["green"] = curses.COLOR_GREEN
        Colors.__colors["blue"] = curses.COLOR_BLUE
        Colors.__colors["cyan"] = curses.COLOR_CYAN
        Colors.__colors["magenta"] = curses.COLOR_MAGENTA
        Colors.__colors["yellow"] = curses.COLOR_YELLOW
        Colors.__colors_num = 8
    
        Colors.__color_pairs["default"] = 0
        self.add_pair("reverse", self.color("black"), self.color("white"))
        
    @staticmethod
    def add_color( name, r, g, b):
        Colors.__log.debug("adding color %s: (%s, %s, %s)", name, r, g, b)
        try:
            curses.init_color(Colors.__colors_num + 1, r, g, b)
            Colors.__colors[name] = Colors.__colors_num
            Colors.__colors_num+=1
            Colors.__log.debug("color num: %s", Colors.__colors_num)
        except curses.error as e:
            Colors.__log.exception(e)
        
        
    @staticmethod
    def add_pair( name, fg, bg):
        Colors.__log.debug("adding pair %s: (%s, %s)", name, fg, bg)
        try:
            curses.init_pair(Colors.__pairs_num + 1, fg, bg)
            Colors.__color_pairs[name] = curses.color_pair(Colors.__pairs_num+1)
            Colors.__pairs_num+=1
            Colors.__log.debug("pair num: %s", Colors.__pairs_num)
        except curses.error as e:
            Colors.__log.exception(e)
    
    @staticmethod
    def color(name):
        num = Colors.__colors.get(name, curses.COLOR_WHITE)
        Colors.__log.debug("getting color num %s", num)
        return num
    
    @staticmethod
    def pair(name):
        num = Colors.__color_pairs.get(name, curses.color_pair(0))
        Colors.__log.debug("getting pair %s", num)
        return num        
    
class Box_system:
    def __init__(self, stdscr):
        Box_system.__log = logging.getLogger("Box_system")
        Box_system.__log.info("Starting Box_System")
        Box_system.__running = True
        Box_system.debug=True
        
        Box_system.__entities_list = []
        
        #=============================
        #== window content settings ==
        #=============================
        #list of window contents
        Box_system.__window_content_list = dict()
        #name of current content
        Box_system.__current_content = None
        
        #=====================
        #== curses settings ==
        #=====================
        #avoid MOUSE_CLICK - just MOUSE_PRESS and MOUSE_RELEASE
        #cant find double clicks
        curses.mouseinterval(0)
        #setting curses to look just for left and right clicks
        curses.mousemask(curses.BUTTON1_CLICKED + curses.BUTTON3_CLICKED)
        #making cursor unvisible
        curses.curs_set(0)
        
        
        #window data
        Box_system.__root_win = stdscr
        Box_system.height, Box_system.width = stdscr.getmaxyx()
        Box_system.__log.debug("screen size: %s", console_point(Box_system.height, Box_system.width))
        
        Colors()
        
        Box_system.__log.info("Starting subsystems...")
        try:
            Box_system.text_system = Text_system("text_system")
            Box_system.collider_system = Collider_system("collider_system")
            Box_system.input_system = Input_system("input_system")
            Box_system.keyboard_manipulation_system = Keyboard_manipulation_system("keyboard_manipulation_system")
        except Exeception as e:
            Box_system.__log.exception(e)
            Box_system.__running = False
        else:
            Box_system.__log.info("...subsytems start done")
    
    @staticmethod
    def refresh():
        """This function refresh all entities registered in systems"""
        Box_system.__log.debug("======= REFRESHING ========")
        Box_system.__root_win.clear()
        
        if Box_system.keyboard_manipulation_system.shown_pointer:
            Box_system.keyboard_manipulation_system.shown_pointer = False
            
        Box_system.text_system.draw()
        
        Box_system.__log.debug("refreshing curses")
        Box_system.__root_win.refresh()
        Box_system.__log.debug("====== REFRESH DONE =======")
    
    
    
    @staticmethod
    def add_entity(ent):
        Box_system.__log.debug("adding entity: %s", ent)
        bisect.insort_left(Box_system.__entities_list, ent)
        Box_system.__log.debug("num of entities: %s", len(Box_system.__entities_list))
        
    @staticmethod
    def delete_registered_entities():
        Box_system.__log.info("deleting entities in number: %s", len(Box_system.__entities_list))
        while len(Box_system.__entities_list):
            Box_system.__entities_list[0].finish()
            del Box_system.__entities_list[0]
            
    @staticmethod
    def add_window_content(name, content_func):
        Box_system.__log.debug("adding window content - <%s, %s>", name, content_func)
        if type(content_func) == types.FunctionType:
            Box_system.__window_content_list[name] = content_func
    
    @staticmethod
    def set_window_content(name):
        if Box_system.__current_content == name:
            return
        
        Box_system.__log.info("setting content: %s", name)
        #if doesnt exist - KeyError
        func = Box_system.__window_content_list[name]
        
        if Box_system.__current_content != None:
            Box_system.delete_registered_entities()    
        Box_system.__current_content = name
        
        func()
        
        Box_system.refresh()
            
    @staticmethod
    def wait_for_key():
        key = Box_system.__root_win.getch()
        Box_system.__log.debug("keypress: %s", key)
        
        #pseudo key KEY_MOUSE
        if key == 409:
            
            try:
                ID, mx, my, mz, btn = curses.getmouse()
                Box_system.__log.debug("mouse data ID: %s (%s,%s) - btn: %s", ID, my, mx, btn)
                Box_system.collider_system.check_click(ID, mx, my, mz, btn)
            except curses.error as e:
                pass
                
        #flag to exit
        elif key == 1:
            Box_system.__running = False
        
        #arrows and TAB
        elif key==259 or key == 258 or key == 261 or key == 260 or key == 9 or key == 353:
            Box_system.keyboard_manipulation_system.move_pointer(key)
        
        #enter
        elif key == 10:
            if Box_system.keyboard_manipulation_system.shown_pointer:
                Box_system.keyboard_manipulation_system.execute_pointed()
    
    @staticmethod      
    def get_input_data(*entities):
        return Box_system.input_system.get_inputs(*entities)
    
    @staticmethod
    def get_win_size():
        y, x = Box_system.__root_win.getmaxyx()
        return console_point(y, x)
    
    @staticmethod
    def is_running():
        return Box_system.__running
    
    @staticmethod
    def get_current_content():
        return Box_system.__current_content
    
    @staticmethod
    def get_root_window():
        return Box_system.__root_win
    @staticmethod
    def stop():
        Box_system.delete_registered_entities()
        Box_system.__running = False
                

"""
    =============
    == SYSTEMS ==
    =============
"""

class basic_system:
    def __init__(self, name):
        self._components_list = []
        self.name = name
        self._log = logging.getLogger(name)
        self._id_counter = 1

    def add_component(self, comp):
        self._log.debug("adding component")
        self._id_counter +=1
        self._components_list.append(comp)
        return self._id_counter-1

    def remove_component(self, comp):
        self._log.debug("removing component")
        self._components_list.remove(comp)

class Text_system(basic_system):
    def __init__(self, name):
        basic_system.__init__(self, name)
        self._log.info("text system started")
        
    def draw(self):
        #self._log.debug("drawing content of all listed entites with text component...")
        for i in range(len(self._components_list)-1, -1, -1):
            comp = self._components_list[i]
            
            ent = comp.entity
            
            win = ent.get_win()
            
            border = comp.border
            b_ch = comp.border_ch
            
            content = comp.get_content()
            offset = comp.get_offset()
            
            color_pair = comp.color
            
            #logs
            #self._log.debug("%s", ent.name.upper())
            #self._log.debug("color: %s", color_pair)
            
            #setting border
            if border:
                win.border(b_ch[0],
                           b_ch[1],
                           b_ch[2],
                           b_ch[3],
                           b_ch[4],
                           b_ch[5],
                           b_ch[6],
                           b_ch[7])
            
            
            
            #printing content
            #self._log.debug("adding to curses stack")
            try:
                y = 0
                for line in content:
                    if len(line) >= ent.dimentions.x:
                        line = line[:ent.dimentions.x - 1]
                    win.addstr(offset.y+y, offset.x, line, color_pair)
                    y+=1
            except curses.error as e:
                self._log.exception(e)
                self._log.warning("overflow of content - cutting it")
                pass
            else:
                #self._log.debug("...draw of %s done", ent.name)
                pass

class Collider_system(basic_system):
    def __init__(self, name):
        basic_system.__init__(self, name)
        
        #matrix to collider (y, x)
        #every cell of matrix contains a list
        #in list are pointers to entities
        #last pointer is always on top
        #when unregistered, removing pointers from cells
        self.__matrix = []
        for i in range(Box_system.height):
            self.__matrix.append([])
            for j in range(Box_system.width):
                self.__matrix[i].append([])
        self.__clicked = None
        
        self._log.debug("matrix y: %s", len(self.__matrix))
        self._log.debug("matrix x: %s", len(self.__matrix[0]))
        self._log.debug("matrix[0][0]: %s", self.__matrix[0][0])
        
        self._log.info("collider system started")
    
    def add_component(self, comp):
        self._log.debug("adding component")
        self._components_list.append(comp)
        self._id_counter +=1
        
        start = comp.start_point
        self._log.debug("adding pointers from %s to %s", start, start+comp.lengths)
        
        for y in range(comp.lengths.y):
            for x in range(comp.lengths.x):
                self.__matrix[start.y + y][start.x + x].append(comp.entity)
        return self._id_counter-1

    def remove_component(self, comp):
        self._log.debug("removing component")
        self._components_list.remove(comp) 
        
        start = comp.start_point
        
        for y in range(comp.lengths.y):
            for x in range(comp.lengths.x):
                self.__matrix[start.y+y][start.x + x].remove(comp.entity)
    
    def check_click(self, ID, mx, my, mz, btn):
        if btn == curses.BUTTON1_PRESSED:
            #checking in matrix if that click hit something
            if len(self.__matrix[my][mx]) > 0:
                
                #get the last entity in list (its on the top)
                ent = self.__matrix[my][mx][-1]
                self._log.debug("matrix[%s][%s]: %s", my, mx, self.__matrix[my][mx])
                self._log.debug("found entity: %s", ent)
                
                #start click function of entity
                ent.click()
                self.__clicked = ent
                
                #sending ata to KMS that its good to make a pointer there
                Box_system.keyboard_manipulation_system.set_pointed(ent)
        elif btn == curses.BUTTON1_RELEASED:
            if self.__clicked != None:
                self.__clicked.unclick()
                self.__clicked = None
    
    def check_unclick(self):
        if self.__clicked != None:
            self.__clicked.unclick()
            self.__clicked = None
        

class Input_system(basic_system):
    def __init__(self, name):
        basic_system.__init__(self, name)
        self._log.info("input system started")
    
    def get_inputs(self, *entities):
        out = dict()
        comps = []
        
        for ent in entities:
            try:
                comps.append(ent.input_component)
            except AttributeError as e:
                self._log.exception(e)
                self._log.error(ent.name)
                pass
                
        for comp in comps:
            for c in self._components_list:
                if c.get_id == comp.get_id and comp.is_registered():
                    out[c.entity.name] = c.get_last_input()
                    
        return out
    
class Keyboard_manipulation_system(basic_system):
    UP_NEIGH = 0
    RIGHT_NEIGH = 1
    DOWN_NEIGH = 2
    LEFT_NEIGH = 3
    
    def __init__(self, name):
        basic_system.__init__(self, name)
        
        self.__pointed = None
        self.__old_ch = " "
        self.shown_pointer = False
        
        self._log.info("keyboard manipulation system started")
    
    def move_pointer(self, key):
        
        if self.__pointed == None:
            try:
                self._log.debug("creating start entity")
                self.__pointed = self._components_list[0].entity
                self.__mark_pointed()
                Box_system.refresh()
            except IndexError as e:
                pass
                self._log.debug("there is no entity to point - doing nothing")
        elif self.shown_pointer == False:
            self.__mark_pointed()
        else:
            if key == 259 or key == 353:
                index = Keyboard_manipulation_system.UP_NEIGH
            elif key == 258 or key == 9:
                index = Keyboard_manipulation_system.DOWN_NEIGH
            elif key == 260:
                index = Keyboard_manipulation_system.LEFT_NEIGH
            else:
                index = Keyboard_manipulation_system.RIGHT_NEIGH
            
            next_ent = self.__pointed.key_man_component.get_neighbour(index)
                
            if next_ent != None:
                if self.shown_pointer: self.unmark_pointed()
                self.__pointed = next_ent
                self.__mark_pointed()
                
    def __mark_pointed(self):
        if self.__pointed is not None:
            self._log.debug("marking %s", self.__pointed.name)
            point = self.__pointed.get_absolute_position()
            
            if point.x - 1 >= 0 :
                point.x -= 1
            
            #setting mark
            root = Box_system.get_root_window()
            root.addch(point.y, point.x, '+')
            root.refresh()
            self.shown_pointer = True
    
    def unmark_pointed(self):
        self._log.debug("unmarking %s", self.__pointed.name)
        self.shown_pointer = False
        Box_system.refresh()
        
    def add_component(self, comp):
        basic_system.add_component(self, comp)
        
        if comp.is_start():
            self._log.debug("setting start entity %s", comp.entity.name)
            self.__pointed = comp.entity
    
    def remove_component(self, comp):
        self._log.debug("removing component")
        self._components_list.remove(comp)
        
        if self.__pointed == comp.entity:
            self.__pointed = None
        
    def set_pointed(self, ent):
        try:
            comp = ent.key_man_component
        except AttributeError as e:
            self._log.exception(e)
            pass
        else:
            self.__pointed = ent
    
    def execute_pointed(self):
        #execute click and unclick function of pointed entity
        #keyboard_manipulation_component should be combined with collider component
        try:
            self.__pointed.click()
            curses.napms(100)
            self.__pointed.unclick()
            self.__mark_pointed()
        except AttributeError as e:
            self._log.exception(e)
        
                
"""
    ================
    == COMPONENTS ==
    ================
"""

class basic_component:
    def __init__(self, entity, system, reg=True):
        self.entity = entity
        self._system = system
        self._registered = False
        self._ID = None
        
        if reg:
            self.register()
        
        entity.add_component(self)
        
    def register(self):
        if not self._registered:
            self._ID = self._system.add_component(self)
            self._registered = True

    def unregister(self):
        if self._registered:
            self._system.remove_component(self)
            self._ID = None
            self._registered = False
    
    def reinitialize(self):
        self.unregister()
        self.register()
        
    def is_registered(self):
        return self._registered
    
    def get_id(self):
        return self._ID
    
    def __repr__(self):
        return "component of "+self.entity.name+" - ID:"+str(self._ID)

class Text_component(basic_component):
    def __init__(self, entity, cont, color, offy, offx, border, border_ch, fit):
        self.__log = logging.getLogger("text_comp_"+entity.name)
        self.__log.debug("Initializing text component")
        
        basic_component.__init__(self, entity, Box_system.text_system)
        
        #border attributes
        self.__log.debug("setting dimentions attributes dependly to flags")
        self.border = border
        self.border_ch = border_ch
        self.color = color
        self.__fit = fit
        self.__offset = console_point(offy, offx)
        
        if self.border:
            self.__offset.x += 1
            self.__offset.y += 1
            
        self.__log.debug("border: %s", border)
        self.__log.debug("offset: %s", self.__offset)        
        self.__log.debug("fit: %s", self.__fit)
            
        #making sure, that content is a list
        self.set_content(cont)
        
        #changing dimentions because of fit flag
        if self.__fit:
            self.__fit_dimensions()
        elif self.border:
            self.entity.dimentions.y += 2
            self.entity.dimentions.x += 2
        
        self.__log.debug("initialzation done")
    
    def __fit_dimensions(self):
        self.__log.debug("fitting dimentions to content")
        ent = self.entity
        ent.dimentions.y = len(self.__content)
        x= 0
        for line in self.__content:
            x = max(x, len(line))
        ent.dimentions.x = x + 1
        
        #changing size because of border
        if self.border:
            ent.dimentions.y+=2
            ent.dimentions.x+=1    

    def set_content(self, cont):
        if type(cont) == str:
            self.__content = cont.split("\n")
        else:
            self.__content = cont
        self.__log.debug("setting content:\n%s", self.__content)

    def get_content(self):
        return self.__content

    def change_offset(self, oy, ox):
        self.__offset = console_point(oy, ox)

    def get_offset(self):
        return self.__offset

class Collider_component(basic_component):
    def __init__(self, entity, dimentions, outline):
        self.__log = logging.getLogger("coll_comp_"+entity.name)
        self.__log.debug("initializing collider component")
        
        self.start_point = entity.get_absolute_position()
        self.__outline = outline
        self.start_point.y -= outline
        self.start_point.x -= outline
        
        self.lengths = console_point(dimentions.y + 2*outline, dimentions.x + 2*outline)
        
        basic_component.__init__(self, entity, Box_system.collider_system)        
        self.__log.debug("initialization done")
    
    def reinitialize(self):
        self.unregister()
        
        self.__log.debug("reinitialized absolute position: %s", self.entity.get_absolute_position())
        self.start_point = self.entity.get_absolute_position()
        self.start_point.y -= self.__outline
        self.start_point.x -= self.__outline
        
        
        self.register()
        
class Input_component(basic_component):
    def __init__(self, entity, passwd):
        self.__log = logging.getLogger("input_comp_"+entity.name)
        self.__log.debug("initializing input component")
        
        self.__txtpad = curses.textpad.Textbox(entity.get_win())
        self.__txtpad.stripspaces = 1
        
        #this variable checks if someone left Textbox with eg. Tab button
        #and sends this key to Box_system to analize that
        self.__left = 0
        
        self.__last_input = ""
        self.__passwd = passwd
        
        self.__log.debug("passwd: %s", self.__passwd)
        
        basic_component.__init__(self, entity, Box_system.input_system)
        
        if self.__passwd:
            #fake win is matrix which contains real input of user, but user will see just '*' characters
            self.__fake_win = []
            
            for i in range(self.__txtpad.maxy + 1):
                self.__fake_win.append([])
                for j in range(self.__txtpad.maxx + 1):
                    self.__fake_win[i].append(0x20)
            
            self.fake_data = ""
        
        self.__log.debug("initialization done")
        
    def reinitialize(self):
        self.unregister()
        
        #del self.__txtpad
        self.__txtpad = curses.textpad.Textbox(self.entity.get_win())
        self.__txtpad.stripspaces = 1
        
        self.register()
    
    def get_input(self):
        self.__log.debug("showing cursor")
        curses.curs_set(1)

        if self.__passwd:
            self.__fill_fake_win()
            self.fake_data = self.__txtpad.edit(self.__pass_validator)
            self.__log.debug("fake data:%s", self.fake_data)
            self.__last_input = self.__gather_fake_win()
        else:
            self.__last_input = self.__txtpad.edit(self.__validator)
        
        #vanishing cursor
        self.__log.debug("vanishing cursor")
        curses.curs_set(0)
        
        #removing last space from input
        self.__last_input = self.__last_input[:-1]
        
        self.__log.debug("last_input:%s", self.__last_input)
        
        #analizing left action from Textbox
        if self.__left > 0:
            curses.ungetch(self.__left)
            
            if self.__left == 409:
                curses.ungetmouse(*self.__mouse_left)
                #sending unclick because Box_system has to unclick once clicked entity
                curses.ungetch(409)
                curses.ungetmouse(self.__mouse_left[0], self.__mouse_left[1], self.__mouse_left[2], self.__mouse_left[3], curses.BUTTON1_RELEASED)
                
                self.__mouse_left = ()
                
            self.__left = 0
    
    def get_last_input(self):
        return self.__last_input

    def is_pass(self):
        return self.__passwd
    
    #functions to manipulate fake window matrix
    def __delch_fake_win(self, y, x):
        self.__log.debug("delch_fake_win(%s, %s)", y, x)
        if y <= self.__txtpad.maxy and x <= self.__txtpad.maxx and y >= 0 and x >= 0:
            for i in range(x, self.__txtpad.maxx):
                self.__fake_win[y][i] = self.__fake_win[y][i+1]
            self.__fake_win[y][self.__txtpad.maxx]= 0x20
    
    def __EOL_fake_win(self, y):
        self.__log.debug("EOL_fake_win(%s)", y)
        if y >= 0 and y <= self.__txtpad.maxy:
            x = self.__txtpad.maxx
            while x >= 0 and self.__fake_win[y][x] == 0x20:
                x -= 1
                
            if x+1 > self.__txtpad.maxx:
                return self.__txtpad.maxx
            return x+1

    def __clearln_fake_win(self, y, x):
        self.__log.debug("clearln_fake_win(%s, %s)", y, x)
        if y <= self.__txtpad.maxy and x <= self.__txtpad.maxx and y >= 0 and x >= 0:
            for i in range(x, self.__txtpad.maxx + 1):
                self.__fake_win[y][i] = 0x20
                
    def __deleteln_fake_win(self, y, x):
        self.__log.debug("deleteln_fake_win(%s, %s)", y, x)
        if y <= self.__txtpad.maxy and x <= self.__txtpad.maxx and y >= 0 and x >= 0:
            #clearing first line
            self.__clearln_fake_win(y, 0)
            
            #moving evry line one up
            for my in range(y, self.__txtpad.maxy):
                for mx in range(self.__txtpad.maxx + 1):
                    self.__fake_win[my][mx] = self.__fake_win[my+1][mx]
            
            #clearing the last line
            self.__clearln_fake_win(self.__txtpad.maxy, 0)
    
    def __insertln_fake_win(self, y):
        self.__log.debug("insertln_fake_win(%s)", y)
        if y >= 0 and y <= self.__txtpad.maxy:
            #moving whole content one line down
            for my in range(self.__txtpad.maxy, y, -1):
                for mx in range(self.__txtpad.maxx + 1):
                    self.__fake_win[my][mx] = self.__fake_win[my-1][mx]
            
            #clearing inserted line
            self.__clearln_fake_win(y, 0)
    
    def __gather_fake_win(self):
        self.__log.debug("gather_fake_win()")
        y = 0
        s = ""
        for line in self.__fake_win:
            last = self.__EOL_fake_win(y)
            
            if last >0:
                for x in range(last+1):
                    #similiar workaround for special characters like in TextBox object
                    s += chr(self.__fake_win[y][x] % 256)
        
                s+='\n'
            y+=1
        
        if y == 1:
            return s[:-1]
        return s
            
    def __fill_fake_win(self):
        self.__log.debug("filling fake window with data on screen")
        win = self.entity.get_win()
        
        for i in range(self.__txtpad.maxy + 1):
            for j in range(self.__txtpad.maxx + 1):
                self.__fake_win[i][j] = win.inch(i, j)
        
        #moving cursor back on the end of first line
        x = self.__EOL_fake_win(0)
        self.__log.debug("moving cursor back on the begining")
        win.move(0, x)
        
    
    #validators
    def __validator(self, ch):
        #termination buttons
        if ch == 9:#TAB
            self.__left = ch
            return 7 #termination
        elif ch == 353: #RTAB
            self.__left = ch
            return 7
        elif ch == 409: #KEY_MOUSE
            try:
                ID, mx, my, mz, btn = curses.getmouse()
            except curses.error as e:
                self.__log.debug("%s", e.args)
            else:
                p1 = self.entity.get_absolute_position()
                p2 = p1 + self.entity.dimentions
                
                if mx >= p1.x and mx <= p2.x and my >= p1.y and my <= p2.y:
                    pass
                else:
                    self.__left = ch
                    self.__mouse_left = (ID, mx, my, mz, btn)
                    return 7
            
        return ch
    
    def __pass_validator(self, ch):
        """
        this validator saves every data collected to fake window,
        because every printable character is converted to '*' sign
        
        Every other operation is executed on either fake win matrix or TextBox object
        """
        #self.__log.debug("pass_validator - key: %s", ch)
        
        
        y, x = self.entity.get_win().getyx()
        
        #termination buttons
        if ch == 9:#TAB
            self.__left = ch            
            return 7 #termination
        elif ch == 353: #RTAB
            self.__left = ch
            return 7
        elif ch == 409: #KEY_MOUSE
            try:
                ID, mx, my, mz, btn = curses.getmouse()
            except curses.error as e:
                self.__log.debug("%s", e.args)
            else:
                self.__log.debug("pass_validator - mouse data: (%s, %s, %s, %s, %s)", ID, mx, my, mz, btn)
                
                p1 = self.entity.get_absolute_position()
                p2 = p1 + self.entity.dimentions
                
                #if mouse click is beyond the TextBox, terminationg and resending it to Box_system
                if mx >= p1.x and mx <= p2.x and my >= p1.y and my <= p2.y:
                    pass
                else:
                    self.__left = ch
                    self.__mouse_left = (ID, mx, my, mz, btn)
                    return 7        
        
        #printable characters
        elif ch >= 0x20 and ch <= 0x7e:
            self.__fake_win[y][x] = ch
            #user will see only '*' characters
            return 0x2a # *
        #delete character (before cursor)
        elif ch in (curses.ascii.BS, curses.KEY_BACKSPACE):    # ^h, backspace
            self.__delch_fake_win(y, x-1)
        #delete character (on the cursor)    
        elif ch == curses.ascii.EOT:                           # ^d
            self.__delch_fake_win(y, x)
        #delete line on cursor position
        elif ch == curses.ascii.VT:                            # ^k
            if x == 0 and self.__EOL_fake_win(y) == 0:
                self.__deleteln_fake_win(y, x)
            else:
                self.__clearln_fake_win(y, x)
        #insert line on cursor position
        elif ch == curses.ascii.SI:                            # ^o
            self.__insertln_fake_win(y)  
            
        return ch        


class Keyboard_manipulation_component(basic_component):
    UP_NEIGH = 0
    RIGHT_NEIGH = 1
    DOWN_NEIGH = 2
    LEFT_NEIGH = 3    
    
    def __init__(self, entity, start):
        self.__log = logging.getLogger("key_man_comp_"+entity.name)
        self.__log.debug("initializing keyboard manipulation component")
        
        self.__neighbours = [None,#UP
                             None,#RIGHT
                             None,#DOWN
                             None]#LEFT
        self.__start = start
        
        basic_component.__init__(self, entity, Box_system.keyboard_manipulation_system)
        
        self.__log.debug("initialization done")
    
    def set_neighbour(self, entity, index):
        if entity != None:
            self.__log.debug("setting neighbour: %s on %s", entity, index)
            if index >= 0 and index <= 3:
                self.__neighbours[index] = entity
            else:
                raise ValueError("Neighbour index is from 0 to 3")
    
    def set_neighbours(self, up, right, down, left):
        self.set_neighbour(up, 0)
        self.set_neighbour(right, 1)
        self.set_neighbour(down, 2)
        self.set_neighbour(left, 3)
    
    def get_neighbour(self, index):
        if index >= 0 and index <= 3:
            return self.__neighbours[index]
        else:
            raise ValueError("Neighbour index is from 0 to 3")
    
    def is_start(self):
        return self.__start
