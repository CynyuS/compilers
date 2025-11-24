"""
Dead Code Elimination

Cynthia Shao and Jonathan Brown

This script takes in a Bril JSON file and outputs a new Bril program 
to stdout with dead code eliminated within every basic block.
"""

import json
import sys
import copy
from collections import defaultdict

class Block:
	def __init__(self, idx, instrs):
		self.idx = idx
		self.instrs = instrs
		self.edges = []

	def labels(self):
		if self.instrs and "labels" in self.instrs[0]:
			return self.instrs[0]["labels"]
		return None

	def label(self):
		if self.instrs and "label" in self.instrs[0]:
			return self.instrs[0]["label"]
		return None

	def last(self):
		if self.instrs:
			return self.instrs[-1]
		return None

	def get_args(self):
		if self.instrs and "args" in self.instrs[0]:
			return self.instrs[0]["args"]
		return None

	def add_edge(self, target):
		if target not in self.edges:
			self.edges.append(target)
	
	def __str__(self):
		return f"Block(idx={self.idx}, label={self.label()}, edges = {self.edges} )"          


def print_block_instrs(blks):
    for (i, instr) in enumerate(blks.instrs):
        print(i, instr)

def print_instructions():
    print("INSTRS")
    for (i, func) in enumerate(bril["functions"]):
        print(i, func)
        if "instrs" in func:
            for (j, instr) in enumerate(func["instrs"]):
                print(j, instr)

bril = json.load(sys.stdin)

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

used_names = defaultdict(int)

def get_unique_block_name(self,lbl):
    if self: 
        first = self[0]
        if "label" in first:
            return first["label"]
        elif "dest" in first:
            d = first["dest"]
            if d in used_names:
                used_names[d] += 1
                return d + "_" + used_names[d]
            return first["dest"]
        elif "funcs" in first:
            return split_func_calls(first["funcs"])
        else:
            return first["op"]
    else:
        return lbl

blocks = []
block = []
selfIdx = 0
func_counter = 0

func_to_blocks = {}
for func in bril["functions"]:
    blocks = []
    block = []
    selfIdx = 0
    key = func["name"]
    if "instrs" in func:
        for instr in func["instrs"]:  # loop over instructions in the function
            if "label" in instr:
                b0 = Block(get_unique_block_name(block, instr["label"]), block)
                selfIdx += 1
                blocks.append(b0)
                block = []
                block.append(instr)
            elif "op" in instr:
                if instr["op"] == "br" or instr["op"] == "jmp" or instr["op"] == "ret":
                    b1 = Block(get_unique_block_name(block, ""), block)
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
    func_to_blocks[key] = blocks

def print_func_block():
    for k in func_to_blocks.keys():
        print(k)
        for b in func_to_blocks[k]:
            print_block_instrs(b)

def create_json_from_blocks(func_to_blocks, og_func):
    funcs_json = []
    for func_name, blocks in func_to_blocks.items():
        orig_func = next((f for f in og_func if f["name"] == func_name), {})
        func_dict = {"instrs": [], "name": func_name}
        if "args" in orig_func:
            func_dict["args"] = orig_func["args"]
        if "type" in orig_func:
            func_dict["type"] = orig_func["type"]
        for block in blocks:
            func_dict["instrs"].extend(block.instrs)
        funcs_json.append(func_dict)
    return {"functions": funcs_json}

def global_dce(blocks):
    changed = False
    alive = set()
    for b in blocks:
        for instr in b.instrs:
            args = None
            if "args" in instr:
                args = instr["args"]
            
            if args is not None:
                for arg in args:
                    alive.add(arg) 
    
    for b in blocks:
        for instr in b.instrs:
            if "dest" in instr:
                if instr["dest"] not in alive:
                    b.instrs.remove(instr)
                    changed = True        
    return changed
        
    

def local_dce(blocks):
    changed = False
    for b in blocks:
        seen = set()
        for instr in reversed(b.instrs):
            if "dest" in instr:
                if instr["dest"] is not None:
                    if instr["dest"] not in seen:
                        seen.add(instr["dest"])
                    else:
                        if instr["op"] is not None:
                            if instr["op"] == "const":
                                b.instrs.remove(instr)
                                changed = True
    return changed


for f in func_to_blocks.keys():
    changed = True
    while(changed):
        changed = False
        changed = changed or global_dce(func_to_blocks[f])
    changed = True
    while(changed):
        changed = False
        changed = changed or local_dce(func_to_blocks[f])
        

new_json = create_json_from_blocks(func_to_blocks, bril["functions"])

json.dump(new_json, sys.stdout, indent=4)