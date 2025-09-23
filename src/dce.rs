use std::collections::{HashSet};
use crate::ast::{Pass, FunctionAST};
use crate::basic_block::BasicBlock;

/// Implement local dead code elimination

pub struct DeadCodeElimination;

impl DeadCodeElimination {
    pub fn new() -> Self {
        DeadCodeElimination
    }

    fn local_dce(&self, block: &mut BasicBlock) {
        let mut alive = HashSet::new();
        for instr in &block.instructions {
            if let Some(args) = instr.get_args() {
                for a in args {
                    alive.insert(a);
                }
            }
        }

        // only keep instructions either cause side effects or are alive
        block.instructions.retain(|instr| {
            if instr.get_dest().is_none(){
                return true;
            }

            if let Some(dest) = instr.get_dest() {
                alive.contains(dest)
            } else {
                true
            }
        })
    }
}

impl Pass for DeadCodeElimination {
    fn apply (&self, function: &mut FunctionAST) {
        for block in function.cfg.blocks.values_mut() {
            self.local_dce(block);
        }
    }
}