use std::collections::{HashMap, HashSet};
use crate::bril_parse::{BrilProgram, BrilInstruction};

/// This module builds up basic blocks and generates a cfg in an edge list format

#[derive(Debug, Clone)]
pub struct Block {
    pub idx: String,
    pub instructions: Vec<BrilInstruction>,
}

impl Block {
    /// The first `op` or `label` of a block might not be unique, we will have to check and 
    /// see if the name already exists, and if so, append it with an index
    pub fn new_with_unique_name(
        instructions: Vec<BrilInstruction>, 
        used_names: &mut HashSet<String>, 
        fallback: &str
    ) -> Self {
        let name = Self::get_unique_name(&instructions, used_names, fallback);
        Block {
            idx: name,
            instructions,
        }
    }
    
    /// In case we want to instantiate a new block knowing that the name will be unique
    pub fn _new(idx: String, instructions: Vec<BrilInstruction>) -> Self {
        Block {
            idx,
            instructions,
        }
    }

    fn get_unique_name(
        instructions: &[BrilInstruction], 
        used_names: &mut HashSet<String>, 
        fallback: &str
    ) -> String {
        let proposed_name = Self::get_block_name(instructions, fallback);
        
        // If the name is already used, generate a fresh one
        if used_names.contains(&proposed_name) {
            Self::fresh_name(&proposed_name, used_names)
        } else {
            used_names.insert(proposed_name.clone());
            proposed_name
        }
    }

    fn fresh_name(base: &str, used_names: &mut HashSet<String>) -> String {
        let mut counter = 1;
        loop {
            let candidate = format!("{}{}", base, counter);
            if !used_names.contains(&candidate) {
                used_names.insert(candidate.clone());
                return candidate;
            }
            counter += 1;
        }
    }

    fn get_block_name(instructions: &[BrilInstruction], fallback: &str) -> String {
        if instructions.is_empty() {
            return fallback.to_string();
        }

        // Look for a label first (labels are most specific and should be unique)
        for instr in instructions {
            if let Some(label) = instr.get_label() {
                return label.to_string();
            }
        }

        // If no label found, use the first instruction's dest or op
        let first = &instructions[0];

        if let Some(dest) = first.get_dest() {
            return dest.to_string();
        }

        if let Some(funcs) = first.get_funcs() {
            let result = funcs.join(", ");
            println!("{}", result);
            return result;
        }

        if let Some(op) = first.get_op() {
            return op.to_string();
        }

        fallback.to_string()
    }

    pub fn last(&self) -> Option<&BrilInstruction> {
        self.instructions.last()
    }
}

pub struct ControlFlowGraph {
    blocks: Vec<Block>,
    edges: HashMap<String, Vec<String>>,
    function_boundaries: Vec<(usize, usize)>, // (start_idx, end_idx) for each function
    used_names: std::collections::HashSet<String>, // Track used block names
}

impl ControlFlowGraph {
    pub fn from_program(program: &BrilProgram) -> Self {
        let mut cfg = ControlFlowGraph {
            blocks: Vec::new(),
            edges: HashMap::new(),
            function_boundaries: Vec::new(),
            used_names: HashSet::new(),
        };

        cfg.build_blocks(program);
        cfg.add_terminators(); // Add explicit terminators for fall-through
        
        // Debug: Print blocks for troubleshooting
        println!("Created blocks:");
        for (i, block) in cfg.blocks.iter().enumerate() {
            println!("  Block {}: '{}' with {} instructions", i, block.idx, block.instructions.len());
            for instr in &block.instructions {
                if let Some(op) = instr.get_op() {
                    println!("    {}", op);
                } else if let Some(label) = instr.get_label() {
                    println!("    label: {}", label);
                }
            }
        }
        
        cfg.build_edges();
        cfg
    }

    fn build_blocks(&mut self, program: &BrilProgram) {
        let mut block_counter = 0;

        // Process each function separately
        for function in &program.functions {
            let function_start = self.blocks.len();
            let mut current_block = Vec::new();

            for instr in &function.instructions {
                if instr.has_label() {
                    // Finish current block before starting new labeled block
                    if !current_block.is_empty() {
                        let block = Block::new_with_unique_name(
                            current_block.clone(), 
                            &mut self.used_names, 
                            &format!("b{}", block_counter)
                        );
                        self.blocks.push(block);
                        current_block.clear();
                        block_counter += 1;
                    }
                    current_block.push(instr.clone());
                } else if let Some(op) = instr.get_op() {
                    current_block.push(instr.clone());
                    
                    // End block on control flow instructions
                    if matches!(op, "br" | "jmp" | "ret") {
                        let block = Block::new_with_unique_name(
                            current_block.clone(), 
                            &mut self.used_names, 
                            &format!("b{}", block_counter)
                        );
                        self.blocks.push(block);
                        current_block.clear();
                        block_counter += 1;
                    }
                } else {
                    current_block.push(instr.clone());
                }
            }

            // End of function - finish any remaining block
            if !current_block.is_empty() {
                let block = Block::new_with_unique_name(
                    current_block.clone(), 
                    &mut self.used_names, 
                    &format!("b{}", block_counter)
                );
                self.blocks.push(block);
                current_block.clear();
                block_counter += 1;
            }

            let function_end = self.blocks.len();
            if function_start < function_end {
                self.function_boundaries.push((function_start, function_end - 1));
            }
        }
    }

    fn build_edges(&mut self) {
        // Now that all blocks have explicit terminators, edge building is simple
        for block in &self.blocks {
            let edges = if let Some(last) = block.last() {
                match last.get_op() {
                    Some("jmp") => {
                        // Jump to specific label(s)
                        last.get_labels().unwrap_or_else(Vec::new)
                    },
                    Some("br") => {
                        // Branch to two possible labels
                        last.get_labels().unwrap_or_else(Vec::new)
                    },
                    Some("ret") => {
                        // Return - no successors
                        vec![]
                    },
                    _ => {
                        // This shouldn't happen after add_terminators
                        vec![]
                    }
                }
            } else {
                // This shouldn't happen after add_terminators
                vec![]
            };

            self.edges.insert(block.idx.clone(), edges);
        }
    }

    fn add_terminators(&mut self) {
        // For each function, add explicit terminators to blocks that need them
        for &(start, end) in &self.function_boundaries.clone() {
            for i in start..=end {
                let needs_terminator = if let Some(last) = self.blocks[i].last() {
                    // Check if last instruction is NOT a terminator
                    !matches!(last.get_op(), Some("br" | "jmp" | "ret"))
                } else {
                    // Empty block needs terminator
                    true
                };

                if needs_terminator {
                    if i == end {
                        // Last block in function - add return
                        let ret_instr = BrilInstruction::new(serde_json::json!({
                            "op": "ret",
                            "args": []
                        }));
                        self.blocks[i].instructions.push(ret_instr);
                    } else {
                        // Not last block - add jump to next block
                        let next_block_name = self.blocks[i + 1].idx.clone();
                        let jmp_instr = BrilInstruction::new(serde_json::json!({
                            "op": "jmp",
                            "labels": [next_block_name]
                        }));
                        self.blocks[i].instructions.push(jmp_instr);
                    }
                }
            }
        }
    }

    pub fn get_edges(&self) -> &HashMap<String, Vec<String>> {
        &self.edges
    }
}
