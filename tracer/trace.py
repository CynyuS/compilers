"""
INTO SSA!
Cynthia Shao

This script takes in a Bril json file and transforms the bril program into SSA.
"""

import json
import sys
from collections import deque
import copy 

# FILE PROCESSING

# with open(sys.argv[1], 'r') as file:
    # instrs = json.load(file)
instrs = json.load(sys.stdin)

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

# INSERT TERMINATORS
def insert_terminators(func_blocks_list, func_cfg_single):
    """Insert explicit jmp instructions for blocks that fall through to their successor"""
    for i, block in enumerate(func_blocks_list):
        # Check if block has a terminator
        last_instr = block.last()
        has_terminator = (last_instr is not None and 
                         "op" in last_instr and 
                         last_instr["op"] in ["br", "jmp", "ret"])
        
        if not has_terminator:
            # This block falls through - insert explicit jmp
            successors = func_cfg_single.get(block.idx, [])
            if len(successors) == 1:
                # Insert jmp to the single successor
                jmp_instr = {
                    "op": "jmp",
                    "labels": [successors[0]]
                }
                block.instrs.append(jmp_instr)
            elif len(successors) == 0:
                # No successors - insert ret
                ret_instr = {
                    "op": "ret"
                }
                block.instrs.append(ret_instr)

# Insert terminators for each function
for func_name, func_blocks_list in func_blocks.items():
    insert_terminators(func_blocks_list, func_cfg[func_name])


# COMPUTING DOMINATOR SET

def find_pred(b_idx, preds, dom):
    pred_list = preds.get(b_idx, [])
    if not pred_list:
        return set()
    result = dom[pred_list[0]].copy() #set intersection of preds like stated in lecture 
    for p in pred_list[1:]:
        result = result & dom[p]
    return result
            
def build_preds(cfg): 
    preds = {b: [] for b in cfg}
    for src, succs in cfg.items():
        for s in succs:
            if s in preds:
                preds[s].append(src)
            else:
                preds[s] = [src]
    return preds

def compute_dominance_for_func(func_blocks_list, func_cfg_single):
    
    # Build predecessors for this function
    preds = build_preds(func_cfg_single)
    # Initialize dominance sets
    dom = {}
    idx_set = []
    for b in func_blocks_list:
        idx_set.append(b.idx)
    idx_set = set(idx_set)

    for b in func_blocks_list:
        if b.idx == func_blocks_list[0].idx:
            dom[b.idx] = {b.idx}
        else:
            dom[b.idx] = idx_set.copy()
    
    while True:
        prev_dom = {}
        for k in dom:
            v = dom[k]
            temp = set(v)
            prev_dom[k] = temp
        for b in func_blocks_list:
            if b.idx == func_blocks_list[0].idx:
                continue
            dom[b.idx] = {b.idx}.union(find_pred(b.idx, preds, dom))
        if dom == prev_dom:
            break
    
    sorted_dom = {k: sorted(list(v)) for k, v in sorted(dom.items())}

    return dom, preds

# Compute dominance for each function
for func_name, func_blocks_list in func_blocks.items():
    dom, preds = compute_dominance_for_func(func_blocks_list, func_cfg[func_name])
    func_dom[func_name] = dom
    func_preds[func_name] = preds
    func_sorted_dom[func_name] = {k: sorted(list(v)) for k, v in sorted(dom.items())}

# DOMINANCE FRONTIER

def create_frontier(dom_sets, preds, cfg, func_blocks_list):
    """
    Compute the dominance frontier using the definition:
    DF(X) = {Y | X dominates a predecessor of Y, but X does not strictly dominate Y}
    """
    frontier = {node: set() for node in dom_sets}
    entry_block = func_blocks_list[0].idx if func_blocks_list else None

    # For each node Y in the graph
    for y in dom_sets:
        preds_y = preds.get(y, [])
        
        # Skip nodes with no predecessors (except entry with back edges)
        if not preds_y:
            continue
        
        # For each predecessor P of Y
        for p in preds_y:
            # Start from P and walk up the dominator tree
            runner = p
            
            # Keep going until we reach a node that strictly dominates Y
            while runner is not None:
                # Check if runner strictly dominates Y
                # (runner is in Y's dominator set AND runner != Y)
                if runner in dom_sets.get(y, set()) and runner != y:
                    # runner strictly dominates Y, so we stop
                    break
                
                # runner does not strictly dominate Y, so Y is in DF(runner)
                frontier[runner].add(y)
                
                # Move up to the immediate dominator
                runner = get_idom(runner, dom_sets)
    
    return frontier

def get_idom(node, dom_sets):
    """
    Get the immediate dominator of a node.
    The immediate dominator is the unique dominator that is closest to the node.
    """
    if node not in dom_sets:
        return None
    
    node_doms = dom_sets[node]
    
    # Find the dominator with the largest dominator set (closest to node)
    idom = None
    max_size = -1
    
    for d in node_doms:
        if d == node:
            continue
        
        d_doms = dom_sets.get(d, set())
        
        # Check if d dominates all other dominators of node (except node itself)
        dominates_all = True
        for other in node_doms:
            if other != node and other != d:
                if other not in d_doms:
                    dominates_all = False
                    break
        
        if dominates_all and len(d_doms) > max_size:
            idom = d
            max_size = len(d_doms)
    
    return idom

# Compute the dominance frontier for each function
for func_name in func_blocks.keys():
    func_DF[func_name] = create_frontier(func_dom[func_name], func_preds[func_name], 
                                         func_cfg[func_name], func_blocks[func_name])

# SPLIT ENTRY BLOCKS THAT ARE LOOP HEADERS
for func_name, func_blocks_list in list(func_blocks.items()):
    entry_block = func_blocks_list[0]
    preds = func_preds[func_name]
    
    # Check if entry has back edges
    has_back_edge = entry_block.idx in preds and len(preds.get(entry_block.idx, [])) > 0
    
    if has_back_edge:
        # Create new entry block
        # Remove 'f' prefix if present for the entry name
        base_func_name = func_name[1:] if func_name.startswith('f') else func_name
        new_entry_name = base_func_name + "_entry"
        # Get the label of the entry block (if it has one)
        if entry_block.instrs and "label" in entry_block.instrs[0]:
            target_label = entry_block.instrs[0]["label"]
        else:
            # Entry block has no label, so we'll create one
            # First, we need to add a label to the entry block
            base_func_name = func_name[1:] if func_name.startswith('f') else func_name
            target_label = base_func_name + "_loop_header"
            label_instr = {"label": target_label}
            entry_block.instrs.insert(0, label_instr)
            # Update label mapping
            label_to_block[target_label] = entry_block.idx

        new_entry_instrs = [{
            "op": "jmp",
            "labels": [target_label]
        }]
        new_entry = Block(new_entry_name, new_entry_instrs, True)
        
        # Old entry is no longer the header
        entry_block.is_header = False
        
        # Insert new entry at beginning
        func_blocks_list.insert(0, new_entry)
        func_blocks[func_name] = func_blocks_list
        
        # Update maps
        func_block_maps[func_name][new_entry_name] = new_entry
        block_map[new_entry_name] = new_entry
        
        # Update CFG
        func_cfg[func_name][new_entry_name] = [entry_block.idx]
        
        # Update preds: entry_block now has new_entry as first pred
        old_preds = func_preds[func_name].get(entry_block.idx, [])
        func_preds[func_name][new_entry_name] = []
        func_preds[func_name][entry_block.idx] = [new_entry_name] + old_preds
        
        # Update defs: function args now defined in new entry
        for arg_name in func_defs[func_name]:
            if func_defs[func_name][arg_name] and func_defs[func_name][arg_name][0] == entry_block.idx:
                func_defs[func_name][arg_name][0] = new_entry_name
        
        # Recompute dominance for this function
        dom, preds = compute_dominance_for_func(func_blocks_list, func_cfg[func_name])
        func_dom[func_name] = dom
        func_preds[func_name] = preds
        
        # Recompute DF
        func_DF[func_name] = create_frontier(func_dom[func_name], func_preds[func_name],
                                             func_cfg[func_name], func_blocks[func_name])

# CONVERSION TO SSA

def in_ssa(func_name, blocks, block_map, cfg, dom, DF, variables, defs):
    """ void function that modifies blocks passed into SSA"""
    
    gets_needed = {} #block_idx: set of (var_name, var_type)

    # FIND WHERE TO INSERT GETS - Only for variables with multiple defs
    for v, v_t in variables:
        if v not in defs or len(defs[v]) <= 1:
            # Skip if variable has 0 or 1 definition (no phi needed)
            continue

        # get blocks where variable v is defined
        def_blocks = set(defs[v])

        # using worklist algo compute where we need gets on the frontier
        worklist = list(def_blocks)
        processed = set()

        while worklist:
            block_idx = worklist.pop(0)
            if block_idx in processed:
                continue
            processed.add(block_idx)

            if block_idx in DF:
                # for each block in DF of this block within def blocks of v
                for df_block in DF[block_idx]:
                    # add a get instruction
                    if df_block not in gets_needed:
                        gets_needed[df_block] = set()
                    
                    # Only add if not already there
                    if (v, v_t) not in gets_needed[df_block]:
                        gets_needed[df_block].add((v, v_t))
                        # we created a new def unless its already had a definition
                        if df_block not in processed:
                            worklist.append(df_block)
    
    # INSERT GET INSTRS
    for block_idx, var_set in gets_needed.items():
        if block_idx in block_map:
            block = block_map[block_idx]

            # gets go after labels, or are first thing
            i = 0
            if block.instrs and "label" in block.instrs[0]:
                i = 1
            
            # create get instrs
            get_instrs = []
            for v, v_t in sorted(var_set):
                get = {
                    "dest": v,
                    "type": v_t,
                    "op": "get"
                }
                get_instrs.append(get)
            
            # add all get blocks
            block.instrs = block.instrs[:i] + get_instrs + block.instrs[i:]
    
    # RENAME VARIABLES 

    var_counter = {}
    var_stack = {}
    
    # Track what SSA name each get instruction will produce
    # This maps (block_idx, original_var_name) -> SSA name that the get will produce
    get_ssa_names = {}
    
    # Track the FIRST get SSA name for each variable (this becomes the shadow variable name)
    first_get_name = {}

    # create variable stacks
    for var_name, _ in variables:
        var_stack[var_name] = []
        var_counter[var_name] = 0

    def gen_var_name(var_name):
        count = var_counter[var_name]
        var_counter[var_name] += 1
        return f"{var_name}.{count}"
    
    # FIRST PASS: Determine SSA names for all get instructions in CFG order
    def determine_get_names(block_idx, visited):
        if block_idx in visited or block_idx not in block_map:
            return
        visited.add(block_idx)
        
        block = block_map[block_idx]
        
        # Process get instructions to determine their SSA names
        for instr in block.instrs:
            if "op" in instr and instr["op"] == "get":
                var_name = instr["dest"]
                new_name = gen_var_name(var_name)
                get_ssa_names[(block_idx, var_name)] = new_name
                
                # Track the first get name for this variable (shadow variable name)
                if var_name not in first_get_name:
                    first_get_name[var_name] = new_name
        
        # Visit successors
        for s in cfg.get(block_idx, []):
            determine_get_names(s, visited)
    
    # Run first pass starting from entry block
    if blocks:
        entry_block = blocks[0].idx
        determine_get_names(entry_block, set())
    
    # DON'T reset counters - keep them so second pass continues numbering
    # Only reset stacks for second pass
    for var_name, _ in variables:
        var_stack[var_name] = []
    
    # SECOND PASS: Rename all variables and insert set instructions
    def rename(block_idx, visited):
        if block_idx in visited or block_idx not in block_map:
            return
        visited.add(block_idx)

        block = block_map[block_idx]

        # Save stack state before processing this block
        stack_state = {var: list(stack) for var, stack in var_stack.items()}
        
        # If this is the entry block, push function arguments onto their stacks with ORIGINAL NAMES
        if block_idx == blocks[0].idx:
            for orig_func in instrs["functions"]:
                if "f" + orig_func["name"] == func_name or orig_func["name"] == func_name:
                    if "args" in orig_func:
                        for arg in orig_func["args"]:
                            arg_name = arg["name"]
                            if arg_name in var_stack:
                                var_stack[arg_name].append(arg_name)
                    break

        new_instrs = []

        # Process all instructions
        for i, instr in enumerate(block.instrs):
            new_instr = copy.deepcopy(instr)
            
            # After label (or at start if no label), insert undefs for entry block
            if block_idx == blocks[0].idx and block_idx in gets_needed:
                # Check if this entry block has any predecessors (is a loop header)
                has_predecessors = block_idx in preds and len(preds.get(block_idx, [])) > 0
                
                if not has_predecessors:  # Only initialize if NOT a loop header

                    should_insert = (i == 1 and "label" in block.instrs[0]) or (i == 0 and "label" not in block.instrs[0])
                    
                    if should_insert:
                        for v, v_t in gets_needed[block_idx]:
                            shadow_name = get_ssa_names.get((block_idx, v), None)
                            if shadow_name:
                                if v not in var_stack or not var_stack[v]:
                                    # Variable undefined - create undef
                                    undef_name = gen_var_name(v)
                                    undef_instr = {
                                        "op": "undef",
                                        "dest": undef_name,
                                        "type": v_t
                                    }
                                    new_instrs.append(undef_instr)
                                    
                                    # Set the shadow variable to the undef value
                                    set_instr = {
                                        "op": "set",
                                        "args": [shadow_name, undef_name]
                                    }
                                    new_instrs.append(set_instr)
                                else:
                                    # Variable is defined (e.g., function parameter)
                                    # Set the shadow variable to the current value
                                    curr_val = var_stack[v][-1]
                                    set_instr = {
                                        "op": "set",
                                        "args": [shadow_name, curr_val]
                                    }
                                    new_instrs.append(set_instr)

            # Check if this is a terminator (last instruction)
            is_terminator = (i == len(block.instrs) - 1 and 
                           "op" in instr and 
                           instr["op"] in ["br", "jmp", "ret"])

            # handling get instrs - these DEFINE variables
            if "op" in instr and instr["op"] == "get":
                var_name = instr["dest"]
                # Use the pre-computed SSA name
                new_name = get_ssa_names[(block_idx, var_name)]
                new_instr["dest"] = new_name
                var_stack[var_name].append(new_name)
                
                new_instrs.append(new_instr)
                continue
            
            # rename uses (must come before rename defs)
            if "args" in new_instr:
                new_args = []
                for arg in new_instr["args"]:
                    # find defs for this variable
                    if arg in var_stack and var_stack[arg]:
                        new_args.append(var_stack[arg][-1])
                    else:
                        new_args.append(arg)
                new_instr["args"] = new_args

            # rename defs (regular instructions that define variables)
            if "dest" in new_instr and "op" in new_instr:
                var_name = new_instr["dest"]
                new_name = gen_var_name(var_name)
                new_instr["dest"] = new_name
                if var_name in var_stack:
                    var_stack[var_name].append(new_name)
            
            # If this is a terminator, insert sets BEFORE it
            if is_terminator:
                # Collect all sets needed
                sets_needed = []
                succs = cfg.get(block_idx, [])
                
                # Keep track of which variables we've already set
                vars_set = set()
                
                for s in succs:
                    if s in gets_needed:
                        # for each var that has a get in the successor
                        for v, v_t in gets_needed[s]:
                            # Only insert set once per variable
                            if v not in vars_set:
                                # Check if we have a current definition
                                if v in var_stack and var_stack[v]:
                                    curr_def = var_stack[v][-1]
                                else:
                                    # No definition exists - create an undef
                                    undef_name = gen_var_name(v)
                                    undef_instr = {
                                        "op": "undef",
                                        "dest": undef_name,
                                        "type": v_t
                                    }
                                    new_instrs.append(undef_instr)
                                    curr_def = undef_name
                                    # Push undef onto stack
                                    if v in var_stack:
                                        var_stack[v].append(undef_name)
                                
                                # The shadow variable name is the FIRST get name for this variable
                                shadow_var_name = get_ssa_names.get((s, v), v)
                                
                                set_instr = {
                                    "op": "set",
                                    "args": [shadow_var_name, curr_def]
                                }
                                sets_needed.append(set_instr)
                                vars_set.add(v)
                
                # Add sets before the terminator
                new_instrs.extend(sets_needed)
            
            new_instrs.append(new_instr)
        
        block.instrs = new_instrs

        # Recursively rename successors
        for s in cfg.get(block_idx, []):
            rename(s, visited)
        
        # Restore stack state for other branches
        var_stack.clear()
        var_stack.update(stack_state)

    if blocks:
        entry_block = blocks[0].idx
        rename(entry_block, set())
    
    return blocks

# APPLYING SSA

for func_name, func_blocks_list in func_blocks.items():
    # print(f"CFG for {func_name}: {func_cfg[func_name]}")
    # print(f"doms for {func_name}: {func_dom[func_name]}")
    # print(f"preds for {func_name}: {func_preds[func_name]}")
    # print(f"DF for {func_name}: {func_DF[func_name]}")
    # print(f"Variables: {func_vars[func_name]}")
    # print(f"Defs: {func_defs[func_name]}")
    in_ssa(
        func_name,
        func_blocks_list,
        func_block_maps[func_name],
        func_cfg[func_name],
        func_dom[func_name],
        func_DF[func_name],
        func_vars[func_name],
        func_defs[func_name]
    )
# Output the transformed program
output = {"functions": []}
for func_name, func_blocks_list in func_blocks.items():
    func_instrs = []
    for block in func_blocks_list:
        func_instrs.extend(block.instrs)
    
    # Reconstruct function object
    func_obj = {
        "name": func_name.replace("f", "", 1) if func_name.startswith("f") else func_name,
        "instrs": func_instrs
    }
    
    # Add args and type if they exist in original
    for orig_func in instrs["functions"]:
        if "f" + orig_func["name"] == func_name or orig_func["name"] == func_name:
            if "args" in orig_func:
                func_obj["args"] = orig_func["args"]
            if "type" in orig_func:
                func_obj["type"] = orig_func["type"]
            break
    
    output["functions"].append(func_obj)

print(json.dumps(output, indent=2))