"""
Control Flow Graph!
Jonathan Brown and Cynthia Shao

This script takes in a Bril json file and outputs the 
corresponding control flow graph in a edge list format.
"""
from enum import Enum
import json
import sys

class Table_Occ(Enum):
     IN_TABLE = 1
     NOT_IN_TABLE = 2
     REPLACE = 3
     PRINT_RET = 4
     DONT_USE = 5
     

commutative_instr = ["call", "add", "mul", "and", "or", "eq", "neq"]
#Make var a sort of enum, make var a str, and make idx a num
class LVN_Value:
    def __init__(self, instr, vars): #Instr = string, var1 is the variable index, var2 is the var index
        self.instr = instr 
        if instr in commutative_instr:
            sorted_vars = tuple(sorted(vars))
            self.vars = sorted_vars
        else:
            self.vars = vars
    #TODO: Watch out, subtraction needs the order kept, only for commutative properties, do some sort of checking for add, mul, etc, otherwise do nothing
        
    #TODO: Watch out, const values can be confused for actual vals
    def __eq__(self, other):
        if self.instr == other.instr:
            for (i, var) in enumerate(self.vars):
                for (j, var2) in enumerate(other.vars):
                    if i == j:
                        if type(var) is not type(var2) or var != var2:
                            return False 
            return True
        else:
            return False
    def __str__(self):
        return f"(Instr = {self.instr}, Value = ({self.vars}))"
    __repr__ = __str__

class LVN_Table:
    def __init__(self, idx, value, var):
        self.idx = idx
        self.value = value
        self.var = var 
    def __str__(self):
        return f"(Idx = {self.idx}, Value = {self.value}, Var = {self.var})"
    __repr__ = __str__


class Block:
	def __init__(self, idx, instrs):
		self.idx = idx
		self.instrs = instrs
		self.edges = []

	def label(self):
		if self.instrs and "labels" in self.instrs[0]:
			return self.instrs[0]["labels"]
		return None
	
	def last(self):
		if self.instrs:
			return self.instrs[-1]
		return None

	def add_edge(self, target):
		if target not in self.edges:
			self.edges.append(target)
	
	def __str__(self):
		return f"Block(idx={self.idx}, label={Block.label(self)}, edges = {self.edges} )"          
	__repr__ = __str__
# with open(sys.argv[1], 'r') as file:
# 	instrs = json.load(file)
instrs = json.load(sys.stdin)

blocks = []
block = []
selfIdx = 0

def split_func_calls(funcs): #get funcy
    res = ""
    for (i,func) in enumerate(funcs):
        if i < (len(funcs) - 1):
            res += func + ", "
        else:
            res += func
    return res

def get_block_name(self,lbl):
    if self: 
        first = self[0]
        if "label" in first:
            return first["label"]
        elif "dest" in first:
            return first["dest"]
        elif "funcs" in first:
            return split_func_calls(first["funcs"])
        else:
            return first["op"]
    else:
        return lbl

# creating basic blocks implementation
for func in instrs["functions"]:
    if "instrs" in func:
        for instr in func["instrs"]:  # loop over instructions in the function
            if "label" in instr:
                b0 = Block(get_block_name(block, instr["label"]), block)
                selfIdx += 1
                blocks.append(b0)
                block = []
                block.append(instr)
            elif "op" in instr:
                if instr["op"] == "br" or instr["op"] == "jmp" or instr["op"] == "ret":
                    b1 = Block(get_block_name(block, ""), block)
                    selfIdx += 1
                    block.append(instr)
                    blocks.append(b1)
                    block = []
                else:
                    selfIdx += 1
                    block.append(instr)
        if block:
            b2 = Block(get_block_name(block, ""), block)
            selfIdx += 1
            blocks.append(b2)
            block = []
    
def probe_next(block):
    found = False
    for (i,b) in enumerate(blocks):
        if found: 
            if b.idx != block:
                return b.idx
        if (b.idx) == block:
            found = True

# building the control flow graph edge list!
cfg = {}
for b in blocks:
	last = b.last() # last instr in block, doesn't work if blocks empty
	if last is not None:
		if "op" in last:
			if last["op"] == "jmp":
				if "labels" in last: 
					cfg[b.idx] = last["labels"]
				else:
					cfg[b.idx] = [last["dest"]]
			elif last["op"] == "br":
				cfg[b.idx] = [last["labels"][0], last["labels"][1]]    
			elif last["op"] == "ret":
				cfg[b.idx] = []
			elif "dest" not in last and "labels" not in last:
				cfg[b.idx] = []
			else:
				cfg[b.idx] = [probe_next(b.idx)]
		elif "dest" not in last and "labels" not in last:
			cfg[b.idx] = []
		else:
			cfg[b.idx] = [probe_next(b.idx)]

         



var2num = {}
lvn_list = []
full_lvn_list = []
accepted_ops = ["const", "add", "print", "call", "mul", "id"]
one_arg_ops = ["print", "ret"]
ignore_ops = ["br", "jmp"]
current_idx = 0
offset = 0
free_count = 0

def replace_args(args, arg_repl):
     new_list = []
     for arg in args:
          if arg in arg_repl:
               new_list.append(arg_repl[arg])
          else:
               new_list.append(arg)
     return new_list
     

def createVar2Num(varName):
    global current_idx
    var2num[varName] = current_idx
    #  print(varName)
    current_idx += 1

def getVar2Num(val):
    if len(val) == 2:
        val1 = val[0]
        val2 = val[1]
        if val1 in var2num:
            val1 = lvn_list[var2num[val1]]
        if val2 in var2num:
            val2 = lvn_list[var2num[val2]]
        return (val1, val2)
    else:
        val = val[0]
        if val in var2num:
            val = lvn_list[var2num[val]]
        return (val, None)

def checkValInTable(val):
    for lvn in lvn_list:
        if val == lvn.value:
            return (True, lvn) 
    return (False, None)


def create_lvn_for_arg(instr, arg):
    global current_idx
    var2num[arg] = current_idx
    val = LVN_Value(instr["op"], (None,))
    lvn_comp = LVN_Table(current_idx, val, arg)
    lvn_list.append(lvn_comp)
    current_idx += 1

def argument_checking(instr):
    arg_idx = []
    arg_repl = {}
    for arg in instr["args"]:
        if arg in var2num:
            arg_idx.append(var2num[arg])
            if var2num[arg] < len(lvn_list): 
                arg_repl[arg] = lvn_list[var2num[arg]].var
                # print(f"repl: {arg_repl}")
        else:
            create_lvn_for_arg(instr, arg)
            arg_idx.append(var2num[arg])
    res = replace_args(instr["args"], arg_repl)
    return res, arg_idx

     
#TODO: remove all print(comps) before current_idx +=1 

#Returns (inTable, component)
def createVal(instr, is_const): #TODO: Optimize this lol
    #TODO: Maybe make the subroutines a function
    #TODO: Get rid of code duplication (aka merge const and other instr's inTable route)
    global current_idx
    if is_const: #Deal with consts 
        comp_val = LVN_Value('const', (instr["value"],))
        inTable, lvn_comp = checkValInTable(comp_val)
        if inTable:
            var2num[instr["dest"]] = lvn_comp.idx
            return Table_Occ.IN_TABLE, lvn_comp
        else:
            comp = LVN_Table(current_idx, comp_val, instr["dest"])
            # print(comp)
            current_idx += 1
            var2num[instr["dest"]] = comp.idx
            return Table_Occ.NOT_IN_TABLE, comp 
    else: #Any functions with arguments
        if instr["op"] not in one_arg_ops: #TODO: clean up code, both cases are very similar
            if instr["op"] == "id": #Deal with id cases as they should j be replaced (mostly)
                # print(instr)
                arg = instr["args"][0]
                lvn_comp = None
                if arg in var2num:
                    # print(var2num[arg])
                    # print(lvn_list)
                    var2num[instr["dest"]] = var2num[arg] 
                    lvn_comp = lvn_list[var2num[arg]]
                    if instr["dest"] == lvn_comp.var:
                        return Table_Occ.DONT_USE, None
                else:
                    createVar2Num(arg)
                    var2num[instr["dest"]] = var2num[arg]
                    lvn_val = LVN_Value(instr["op"], (instr["args"][0],))
                    lvn_comp = LVN_Table(current_idx, lvn_val, instr["dest"])
                    return Table_Occ.NOT_IN_TABLE,lvn_comp
                # print(lvn_comp)
                return Table_Occ.REPLACE, lvn_comp
            elif instr["op"] == "call":
                new_args, arg_idx = argument_checking(instr)
                instr["args"] = new_args
                comp_val = LVN_Value(instr["op"], (*arg_idx,))
                comp = LVN_Table(current_idx, comp_val, instr["op"])
                current_idx += 1
                var2num[instr["op"]] = comp.idx
                return Table_Occ.NOT_IN_TABLE, comp
            elif instr["op"] == "store": #TODO: just make some of these functions becuase wowza so much code
                new_args, arg_idx = argument_checking(instr)
                instr["args"] = new_args
                comp_val = LVN_Value(instr["op"], (*arg_idx,))
                comp = LVN_Table(current_idx, comp_val, instr["op"])
                current_idx += 1
                var2num[instr["op"]] = comp.idx
                return Table_Occ.NOT_IN_TABLE, comp
            else:
                new_args, arg_idx = argument_checking(instr)
                instr["args"] = new_args
                comp_val = LVN_Value(instr["op"], (*arg_idx,))
                # print(comp_val)
                inTable, lvn_comp = checkValInTable(comp_val)
                if inTable:
                    if "dest" in instr:
                        if instr["dest"] == lvn_comp.var:
                            return Table_Occ.DONT_USE, None
                        var2num[instr["dest"]] = lvn_comp.idx
                    elif instr["op"] == "free":
                         # Need to free it more than once
                        # print(instr)
                        free_count +=1 
                    else:
                        # print(instr)
                        var2num[instr["funcs"][0]] = lvn_comp.idx
                    return Table_Occ.IN_TABLE, lvn_comp
                else:
                    new_args, arg_idx = argument_checking(instr)
                    instr["args"] = new_args
                    comp_val = LVN_Value(instr["op"], (*arg_idx,))
                    comp = None
                    if "dest" in instr:
                        comp = LVN_Table(current_idx, comp_val, instr["dest"])
                        var2num[instr["dest"]] = comp.idx
                    elif "funcs" in instr:
                        comp = LVN_Table(current_idx, comp_val, instr["funcs"][0])
                        var2num[instr["funcs"][0]] = comp.idx
                    elif instr["op"] == "br":
                        comp = LVN_Table(current_idx, comp_val, instr["op"]) 
                    elif instr["op"] == "free":
                        comp = LVN_Table(current_idx, comp_val, instr["op"])
                    # else: #This is branch ig
                        # print(instr)
                        # Warning("HAHAHAHAHA")
                        # print("MAYDAY SHIP IS SINKING")
                    current_idx += 1
                    return Table_Occ.NOT_IN_TABLE, comp
        else:
            if instr["op"] == "ret":
                if "args" not in instr:
                    return Table_Occ.DONT_USE, None
            new_args, arg_idx = argument_checking(instr)
            instr["args"] = new_args
            comp_val = LVN_Value(instr["op"], (*arg_idx,))
            comp = LVN_Table(current_idx, comp_val, instr["op"])
            # print(comp)
            current_idx += 1
            var2num[instr["op"]] = comp.idx
            return Table_Occ.NOT_IN_TABLE, comp

for b in blocks:
    for (i, instr) in enumerate(b.instrs):
        lvn_val = None
        lvn_component = None
        if "op" in instr and instr["op"] not in ignore_ops:
            if instr["op"] == 'const':
                    inTable, lvn_comp = createVal(instr, True)
                    #TODO: Do something with instr if inTable
                    if inTable == Table_Occ.IN_TABLE:
                            instr["op"] = "id"
                            instr["args"] = [lvn_comp.var]
                            instr["type"] = "int"
                            del instr["value"]
                            if "dest" not in instr:
                                instr["dest"] = "z"
                    else:
                            lvn_list.append(lvn_comp)
            else: 
                inTable, lvn_comp = createVal(instr, False)
                if inTable == Table_Occ.IN_TABLE or inTable == Table_Occ.REPLACE:
                    instr["op"] = "id"
                    instr["args"] = [lvn_comp.var]
                elif inTable == Table_Occ.PRINT_RET:
                    instr["args"] = [lvn_comp.var]
                elif inTable == Table_Occ.DONT_USE:
                     free_count +=1
                    #  print(f"{instr["op"]} has been thrown in the trash")
                else:
                    lvn_list.append(lvn_comp)
    current_idx = 0
    var2num = {}
    lvn_list = []
    full_lvn_list = []


# for l in lvn_list:
#      print(l)
# print(var2num)
# for b in blocks:
#      for instr in b.instrs:
#           print(instr)

# def replace_instrs(instr, ):
# print(instrs)
     
# with open(f"{sys.argv[1]}.out","w") as f: #For some reason works although I didn't edit the instrs directly? YIPEEEEEEE
#     json.dump(instrs, f, indent=4)

json.dump(instrs, sys.stdout, indent=4)
