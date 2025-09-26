use std::collections::{HashSet};
use crate::ast::{Pass, FunctionAST};
use crate::basic_block::BasicBlock;
use crate::bril_parse::{self, BrilInstruction};

/// Answer the question: which variables have statically knowable constant values?

pub struct DataFlow;

impl DataFlow {
    pub fn new() -> Self {
        DataFlow
    }

    pub fn worklist(&self, block: &mut BasicBlock) {
        // in[entry] = init
        // out[*] = init

        // worklist = all blocks
        // while worklist is not empty:
        //     b = pick any block from worklist
        //     in[b] = merge(out[p] for every predecessor p of b)
        //     out[b] = transfer(b, in[b])
        //     if out[b] changed:
        //         worklist += successors of b
    }

    pub fn kills(){
        // calculates what items are overwritten in a basic block, given a set of instructions.
        todo!()
    }

    pub fn transfer(&self, block: &mut BasicBlock, in_consts: &mut HashSet<BrilInstruction>) {
        // CONSTDEF_b union uses that have const args union (in_b - kills_b)
        let curr_const = HashSet::<BrilInstruction>::new();
        let mut const_props = HashSet::<BrilInstruction>::new();
        for instr in &block.instructions {
            // add definitions to set
            if let Some(args) = instr.get_args() {
                // Using fold to check if ALL arguments are constant
                let all_args_constant = args.iter().fold(true, |acc, arg| {
                    acc && (
                        // Check if any instruction in curr_const defines this argument
                        curr_const.iter().any(|const_instr| {
                            const_instr.get_dest().map_or(false, |dest| dest == arg)
                        }) ||
                        // Check if any instruction in in_consts defines this argument
                        in_consts.iter().any(|const_instr| {
                            const_instr.get_dest().map_or(false, |dest| dest == arg)
                        })
                    )
                });
                
                // If all arguments are constant, add this instruction to const_props
                if all_args_constant {
                    const_props.insert(instr.clone());
                }
            }

            // add uses to set
            if let Some(var_dest) = instr.get_dest() {
                if let Some(ops) = instr.get_op() {
                    if ops == "const" {
                        const_props.insert(instr.clone());
                    }
                    // add instructions with different destinations to const_props
                    // don't add instructions from in_consts that would be killed by this instruction
                    const_props.extend(
                        in_consts.iter()
                            .filter(|const_instr| {
                                // only include instructions that define different variables
                                const_instr.get_dest().map_or(true, |dest| dest != var_dest)
                            })
                            .cloned()
                    );
                }
            }
        }

        
    }

    pub fn merge() {
        todo!()
    }
}

impl Pass for DataFlow {
    fn apply (&self, function: &mut FunctionAST) {
        for block in function.cfg.blocks.values_mut() {
            self.worklist(block);
        }
    }
}