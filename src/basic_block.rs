use crate::bril_parse::BrilInstruction;
use std::collections::HashSet;

#[derive(Debug, Clone)]
pub struct BasicBlock {
    pub idx: String,
    pub instructions: Vec<BrilInstruction>,
}

impl BasicBlock {
    pub fn new(idx: String, instructions: Vec<BrilInstruction>) -> Self {
        BasicBlock { idx, instructions }
    }

    pub fn new_with_unique_name(
        instructions: Vec<BrilInstruction>, 
        used_names: &mut HashSet<String>, 
        fallback: &str
    ) -> Self {
        let name = Self::get_unique_name(&instructions, used_names, fallback);
        BasicBlock::new(name, instructions)
    }
    
    fn get_unique_name(
        instructions: &[BrilInstruction], 
        used_names: &mut HashSet<String>, 
        fallback: &str
    ) -> String {
        let proposed_name = Self::get_block_name(instructions, fallback);
        
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

        // Look for a label first
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
            return funcs.join(", ");
        }

        if let Some(op) = first.get_op() {
            return op.to_string();
        }

        fallback.to_string()
    }

    pub fn last(&self) -> Option<&BrilInstruction> {
        self.instructions.last()
    }

    pub fn _is_empty(&self) -> bool {
        self.instructions.is_empty()
    }

    pub fn push_instruction(&mut self, instruction: BrilInstruction) {
        self.instructions.push(instruction);
    }
}