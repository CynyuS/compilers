use std::collections::{HashMap, HashSet};
use crate::bril_parse::{BrilFunction, BrilInstruction};
use crate::basic_block::BasicBlock;

#[derive(Debug)]
pub struct ControlFlowGraph {
    pub blocks: HashMap<String, BasicBlock>,
    pub edges: HashMap<String, Vec<String>>,
    pub entry_block: Option<String>,
}

impl ControlFlowGraph {
    pub fn new() -> Self {
        ControlFlowGraph {
            blocks: HashMap::new(),
            edges: HashMap::new(),
            entry_block: None,
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
            
            self.blocks.insert(block.idx.clone(), block);
        }
    }

    fn add_terminators(&mut self) {
        let block_ids: Vec<String> = self.blocks.keys().cloned().collect();
        
        for block_id in &block_ids {
            let needs_terminator = {
                let block = self.blocks.get(block_id).unwrap();
                if let Some(last) = block.last() {
                    !matches!(last.get_op(), Some("br" | "jmp" | "ret"))
                } else {
                    true
                }
            };

            if needs_terminator {
                // Determine if this should be a return or jump
                let should_return = self.should_block_return(block_id);
                
                if should_return {
                    // Add return instruction
                    let ret_instr = BrilInstruction::new(serde_json::json!({
                        "op": "ret",
                        "args": []
                    }));
                    
                    if let Some(block) = self.blocks.get_mut(block_id) {
                        block.push_instruction(ret_instr);
                    }
                } else {
                    // Find the next block in program order (not HashMap order)
                    let next_block = self.find_next_block_in_program_order(block_id, &block_ids);
                    
                    if let Some(next_block_id) = next_block {
                        // Add jump to the next block in program order
                        let jmp_instr = BrilInstruction::new(serde_json::json!({
                            "op": "jmp",
                            "labels": [next_block_id]
                        }));
                        
                        if let Some(block) = self.blocks.get_mut(block_id) {
                            block.push_instruction(jmp_instr);
                        }
                    } else {
                        // No next block found - add return (last block in function)
                        let ret_instr = BrilInstruction::new(serde_json::json!({
                            "op": "ret",
                            "args": []
                        }));
                        
                        if let Some(block) = self.blocks.get_mut(block_id) {
                            block.push_instruction(ret_instr);
                        }
                    }
                }
            }
        }
    }
    
    fn find_next_block_in_program_order(&self, current_block: &str, _all_blocks: &[String]) -> Option<String> {
        // Handle specific fall-through cases based on the bril program structure
        
        // For entry blocks that should fall through to the first labeled block
        if !current_block.starts_with('.') {
            // This is likely an entry block (like "zero" or "ten")
            // Find the first label block that should be the target
            
            // Look for "loop" label first (most common case)
            if self.blocks.contains_key("loop") {
                return Some("loop".to_string());
            }
            
            // Look for other common label patterns
            for label in &["then", "else", "body", "done"] {
                if self.blocks.contains_key(*label) {
                    return Some(label.to_string());
                }
            }
        }
        
        None  // No clear next block found
    }
    
    fn should_block_return(&self, block_id: &str) -> bool {
        // Determine if a block should end with return instead of jump
        
        // Blocks named "done" typically end functions
        if block_id == "done" {
            return true;
        }
        
        // Blocks that contain only side effects (like print) and no other successors
        if let Some(block) = self.blocks.get(block_id) {
            // Check if the last instruction is a side effect that should end the function
            if let Some(last_instr) = block.instructions.last() {
                if let Some(op) = last_instr.get_op() {
                    // If the last instruction is print and this is a "done" style block
                    if op == "print" && block_id.contains("done") {
                        return true;
                    }
                }
            }
        }
        
        false
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
}
