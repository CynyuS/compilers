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


# with open(sys.argv[1], 'r') as file:
#     instrs = json.load(file)
instrs = json.load(sys.stdin)

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


def split_func_calls(funcs): #get funcy
    res = ""
    for (i,func) in enumerate(funcs):
        if i < (len(funcs) - 1):
            res += func + ", "
        else:
            res += func
    return res

# GLOBAL INSTANTIATIONS

# basic block arrays
blocks = []
block = []

# function headers to basic blocks that are headers
func_headers = {}

# function to variables mappings
func_vars = {}
func_defs = {}

# function to basic blocks under that function mappings
func_blocks = {}  # func_blocks[func_name] = [list of blocks in that function]
block_ref_count = {}
label_to_block = {}

# function to cfg mapping, just constructing cfg out of blocks yields a forest
# want to label the forest by function
func_cfg = {}

# function to dominators mapping
func_dom = {}
# function to predecessors mapping
func_preds = {}

# function to sorted dominator set mapping
func_sorted_dom = {}

# function to dominance frontier mapping
func_DF = {}

# BASIC BLOCK DEFS

class Block:
    def __init__(self, idx, instrs, is_func_header):
        self.idx = idx
        self.instrs = instrs
        self.edges = []
        self.is_header = is_func_header

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

# CONSTRUCTING BASIC BLOCKS

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

def name_in_blocks(name):
    if name == "": 
        return False
    for b in blocks: 
        if b.idx == name:
            return True 
    return False

# ==== INSTANTIATING GLOBAL BASIC BLOCKS ====

for func in instrs["functions"]:
    if "instrs" in func:
        for (i, instr) in enumerate(func["instrs"]):
            if i == 0:
                is_func_header = True
            if "label" in instr:
                # Save the previous block if it exists
                if block:
                    name = get_block_name(block, "")
                    b0 = Block(name, block, is_func_header)
                    if is_func_header == True:
                        b0 = Block("f" + func["name"], block, is_func_header)
                    is_func_header = False
                    blocks.append(b0)
                    block = []
                # Start new block with the label
                block.append(instr)
            elif "op" in instr:
                if instr["op"] == "br" or instr["op"] == "jmp" or instr["op"] == "ret":
                    block.append(instr)
                    name = get_block_name(block, "")
                    b1 = Block(name, block, is_func_header)
                    if is_func_header == True:
                        b1 = Block("f" + func["name"], block, is_func_header)
                    is_func_header = False
                    blocks.append(b1)
                    block = []
                else:
                    block.append(instr)
        # Handle remaining instructions
        if block:
            name = get_block_name(block, "")
            b2 = Block(name, block, is_func_header)
            if is_func_header == True:
                b2 = Block("f" + func["name"], block, is_func_header)
            is_func_header = False
            blocks.append(b2)
            block = []

# Clean up empty blocks
cleanup_arr = []
for (i, block) in enumerate(blocks):
    if block.idx != "":
        cleanup_arr.append(block)
blocks = cleanup_arr

# FUNCTION PROCESSING

# Group blocks by function
for block in blocks:
    if block.is_header:
        current_func = block.idx
        func_headers[current_func] = block
        func_blocks[current_func] = [block]  # Include the header block itself
    else:
        if current_func:
            func_blocks[current_func].append(block)

# block to function lookup
block_map = {block.idx: block for block in blocks}  # Global block map
func_block_maps = {}  # Per-function block maps

for func_name, func_block_list in func_blocks.items():
    func_block_maps[func_name] = {block.idx: block for block in func_block_list}

def get_block(block_idx, func_name=None):
    if func_name and func_name in func_block_maps:
        return func_block_maps[func_name].get(block_idx)
    else:
        return block_map.get(block_idx)

# LABEL MAPPING POST BLOCK PROCESSING

for func_name, func_blocks_list in func_blocks.items():
    for block in func_blocks_list:
        # Check if this block has a label
        if block.instrs and "label" in block.instrs[0]:
            label_name = block.instrs[0]["label"]
            label_to_block[label_name] = block.idx

# VARIABLE PROCESSING

# for each function create the variables
for func_name, blocks in func_blocks.items():
    variables = set()
    func_defs[func_name] = {}
    
    # First, add function arguments as variables
    # Find the original function definition to get its arguments
    for orig_func in instrs["functions"]:
        if "f" + orig_func["name"] == func_name or orig_func["name"] == func_name:
            if "args" in orig_func:
                for arg in orig_func["args"]:
                    arg_name = arg["name"]
                    arg_type = arg["type"]
                    variables.add((arg_name, json.dumps(arg_type, sort_keys=True)))
                    # Function arguments are "defined" at the entry block
                    func_defs[func_name][arg_name] = [blocks[0].idx]
            break
    
    # Then process instructions in blocks
    for block in blocks:
        for instr in block.instrs:
            if "dest" in instr and "type" in instr:
                var_name = instr["dest"]
                var_type = instr["type"]
                variables.add((var_name, json.dumps(var_type, sort_keys=True)))
                # Initialize the list if this is the first time we see this variable
                if var_name not in func_defs[func_name]:
                    func_defs[func_name][var_name] = []
                # Add the block index (not the block object) to the list
                func_defs[func_name][var_name].append(block.idx)
    
    func_vars[func_name] = variables

# CFG PROCESSING

def probe_next_in_func(block_idx, func_blocks_list):
    """Find the next block within a specific function"""
    found = False
    for (i, b) in enumerate(func_blocks_list):
        if found and b.idx != block_idx:
            return b.idx
        if b.idx == block_idx:
            found = True
    return None

def build_cfg_for_func(func_name, func_blocks_list):
    """Build CFG for a single function"""
    cfg = {}
    
    for block in func_blocks_list:
        last = block.last()
        if last is not None and "op" in last:
            if last["op"] == "jmp":
                target_label = last["labels"][0]
                # Map label to actual block name
                target_block = label_to_block.get(target_label, target_label)
                cfg[block.idx] = [target_block]
            elif last["op"] == "br":
                label1 = last["labels"][0]
                label2 = last["labels"][1]
                # Map labels to actual block names
                target1 = label_to_block.get(label1, label1)
                target2 = label_to_block.get(label2, label2)
                cfg[block.idx] = [target1, target2]
            elif last["op"] == "ret":
                cfg[block.idx] = []
            else:
                # Fall through to next block
                next_block = probe_next_in_func(block.idx, func_blocks_list)
                if next_block:
                    cfg[block.idx] = [next_block]
                else:
                    cfg[block.idx] = []
        else:
            # Fall through to next block
            next_block = probe_next_in_func(block.idx, func_blocks_list)
            if next_block:
                cfg[block.idx] = [next_block]
            else:
                cfg[block.idx] = []
    
    return cfg

# Create function-based CFGs
for func_name, func_blocks_list in func_blocks.items():
    func_cfg[func_name] = build_cfg_for_func(func_name, func_blocks_list)

var2num = {}
lvn_list = []
full_lvn_list = []
accepted_ops = ["const", "add", "print", "call", "mul", "id"]
# bool_ops = ["le", "lte", "ge", "gte", "eq"]
one_arg_ops = ["print", "ret"]
ignore_ops = ["br", "jmp", "speculate", "commit"]
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
    # print(lvn_list)
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
    # print(instr)
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
            elif instr["op"] == "call" or instr["op"] == "guard":
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
