use std::collections::{HashMap, HashSet};
use crate::bril_parse::{BrilFunction, BrilInstruction};
use crate::basic_block::BasicBlock;

#[derive(Debug)]
pub struct ControlFlowGraph {
    pub blocks: HashMap<String, BasicBlock>,
    pub edges: HashMap<String, Vec<String>>,
    pub entry_block: Option<String>,
    pub block_order: Vec<String>,
}

impl ControlFlowGraph {
    pub fn new() -> Self {
        ControlFlowGraph {
            blocks: HashMap::new(),
            edges: HashMap::new(),
            entry_block: None,
            block_order: Vec::new(),
        }
    }

    pub fn from_bril_function(function: &BrilFunction) -> Self {
        let mut cfg = ControlFlowGraph::new();
        cfg.build_blocks_from_function(function);
        cfg.add_terminators();
        cfg.build_edges();
        cfg
    }

    fn build_blocks_from_function(&mut self, function: &BrilFunction) {
        let mut block_counter = 0;
        let mut current_block = Vec::new();
        let mut used_names = HashSet::new();

        for instr in &function.instructions {
            if instr.has_label() {
                // Finish current block before starting new labeled block
                if !current_block.is_empty() {
                    let block = BasicBlock::new_with_unique_name(
                        current_block.clone(), 
                        &mut used_names, 
                        &format!("b{}", block_counter)
                    );
                    
                    if self.entry_block.is_none() {
                        self.entry_block = Some(block.idx.clone());
                    }
                    
                    self.block_order.push(block.idx.clone());
                    self.blocks.insert(block.idx.clone(), block);
                    current_block.clear();
                    block_counter += 1;
                }
                current_block.push(instr.clone());
            } else if let Some(op) = instr.get_op() {
                current_block.push(instr.clone());
                
                // End block on control flow instructions
                if matches!(op, "br" | "jmp" | "ret") {
                    let block = BasicBlock::new_with_unique_name(
                        current_block.clone(), 
                        &mut used_names, 
                        &format!("b{}", block_counter)
                    );
                    
                    if self.entry_block.is_none() {
                        self.entry_block = Some(block.idx.clone());
                    }
                    
                    self.block_order.push(block.idx.clone());
                    self.blocks.insert(block.idx.clone(), block);
                    current_block.clear();
                    block_counter += 1;
                }
            } else {
                current_block.push(instr.clone());
            }
        }

        // Finish any remaining block
        if !current_block.is_empty() {
            let block = BasicBlock::new_with_unique_name(
                current_block.clone(), 
                &mut used_names, 
                &format!("b{}", block_counter)
            );
            
            if self.entry_block.is_none() {
                self.entry_block = Some(block.idx.clone());
            }
            
            self.block_order.push(block.idx.clone());
            self.blocks.insert(block.idx.clone(), block);
        }
    }

    fn add_terminators(&mut self) {
        for (i, block_id) in self.block_order.iter().enumerate() {
            let needs_terminator = {
                let block = self.blocks.get(block_id).unwrap();
                if let Some(last) = block.last() {
                    dbg!(block.last());
                    !matches!(last.get_op(), Some("br" | "jmp" | "ret"))
                } else {
                    dbg!(block.last());
                    true
                }
            };

            if needs_terminator {
                if i == self.block_order.len() - 1 {
                    // Last block in function - add return
                    let ret_instr = BrilInstruction::new(serde_json::json!({
                        "op": "ret",
                        "args": []
                    }));
                    
                    if let Some(block) = self.blocks.get_mut(block_id) {
                        block.push_instruction(ret_instr);
                    }
                } else {
                    // Not last block - add jump to next block in order
                    let next_block_id = &self.block_order[i + 1];
                    let jmp_instr = BrilInstruction::new(serde_json::json!({
                        "op": "jmp",
                        "labels": [next_block_id]
                    }));
                    
                    if let Some(block) = self.blocks.get_mut(block_id) {
                        block.push_instruction(jmp_instr);
                    }
                }
            }
        }
    }

    
    fn build_edges(&mut self) {
        for (block_id, block) in &self.blocks {
            let edges = if let Some(last) = block.last() {
                match last.get_op() {
                    Some("jmp") => last.get_labels().unwrap_or_else(Vec::new),
                    Some("br") => last.get_labels().unwrap_or_else(Vec::new),
                    Some("ret") => vec![],
                    _ => vec![],
                }
            } else {
                vec![]
            };

            self.edges.insert(block_id.clone(), edges);
        }
    }

    pub fn _get_edges(&self) -> &HashMap<String, Vec<String>> {
        &self.edges
    }

    pub fn _get_blocks(&self) -> &HashMap<String, BasicBlock> {
        &self.blocks
    }

    pub fn _get_block_order(&self) -> &Vec<String> {
        &self.block_order
    }
}
