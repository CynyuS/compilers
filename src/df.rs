use std::collections::{HashSet, HashMap, VecDeque};
use crate::ast::{Pass, FunctionAST};
use crate::basic_block::BasicBlock;
use crate::bril_parse::{BrilInstruction};

/// Answer the question: which variables have statically knowable constant values?

pub struct DataFlow;

impl DataFlow {
    pub fn new() -> Self {
        DataFlow
    }

    pub fn worklist(&self, cfg: &mut crate::cfg::ControlFlowGraph, args: Option<&Vec<crate::bril_parse::BrilArg>>) -> (HashMap<String, HashSet<BrilInstruction>>, HashMap<String, HashSet<BrilInstruction>>) {
        // Initialize in[*] and out[*] for all blocks
        let mut in_sets: HashMap<String, HashSet<BrilInstruction>> = HashMap::new();
        let mut out_sets: HashMap<String, HashSet<BrilInstruction>> = HashMap::new();
        
        // Initialize worklist with all blocks
        let mut worklist: VecDeque<String> = VecDeque::new();
        
        // Initialize each block's IN and OUT sets
        for block_name in cfg.blocks.keys() {
            // Initialize with empty set first
            let mut initial_set = HashSet::new();
            
            // If this is the entry block, add function arguments as initial constants
            if cfg.entry_block.as_ref() == Some(block_name) {
                if let Some(function_args) = args {
                    for arg in function_args {
                        // Create synthetic instructions for function arguments
                        let arg_instr = BrilInstruction::new(serde_json::json!({
                            "op": "id", // Use "id" not "const" since args aren't compile-time constants
                            "dest": arg.name,
                            "type": arg.arg_type,
                            "args": [format!("param_{}", arg.name)]
                        }));
                        initial_set.insert(arg_instr);
                    }
                }
            }
            

            in_sets.insert(block_name.clone(), initial_set);
            out_sets.insert(block_name.clone(), HashSet::new());
            worklist.push_back(block_name.clone());
        }
        
        // fixed point dataflow analysis
        while let Some(block_name) = worklist.pop_front() {
            // in[b] = merge(out[p] for every predecessor p of b)
            // BUT for entry block, use the initialized set (with function arguments)
            let merged_in = if cfg.entry_block.as_ref() == Some(&block_name) {
                // Entry block: use initialized IN set (which contains function arguments)
                in_sets.get(&block_name).cloned().unwrap_or_default()
            } else {
                // Non-entry block: merge predecessors' OUT sets
                self.merge(&block_name, cfg, &out_sets)
            };
            
            // out[b] = transfer(b, in[b])
            let new_out = if let Some(block) = cfg.blocks.get(&block_name) {
                self.transfer(block, &merged_in)
            } else {
                continue;
            };
            
            // if out[b] changed: worklist += successors of b
            let changed = if let Some(old_out) = out_sets.get(&block_name) {
                &new_out != old_out
            } else {
                true // First time we're setting this
            };
            
            if changed {
                // Add successors to worklist
                if let Some(successors) = cfg.edges.get(&block_name) {
                    for successor in successors {
                        if !worklist.contains(successor) {
                            worklist.push_back(successor.clone());
                        }
                    }
                }
            }
            
            in_sets.insert(block_name.clone(), merged_in);
            out_sets.insert(block_name.clone(), new_out);
        }
        
        (in_sets, out_sets)
    }

    pub fn transfer(&self, block: &BasicBlock, in_consts: &HashSet<BrilInstruction>) -> HashSet<BrilInstruction> {
        // CONSTDEF_b union uses that have const args union (in_b - kills_b)
        let mut out_consts = in_consts.clone();
        
        for instr in &block.instructions {
            if let Some(dest) = instr.get_dest() {
                // Kill any previous definition of this variable
                out_consts.retain(|const_instr| {
                    const_instr.get_dest().map_or(true, |d| d != dest)
                });
                
                // Add new constant if this is a const instruction
                if instr.get_op() == Some("const") {
                    out_consts.insert(instr.clone());
                }
                // For other operations, check if all arguments are constants
                else if let Some(args) = instr.get_args() {
                    let all_const = args.iter().all(|arg| {
                        out_consts.iter().any(|const_instr| {
                            const_instr.get_dest() == Some(arg)
                        })
                    });
                    
                    if all_const {
                        out_consts.insert(instr.clone());
                    }
                }
            }
        }
        
        out_consts
    }

    pub fn merge(
        &self, _block_name: &str, 
        cfg: &crate::cfg::ControlFlowGraph, 
        out_sets: &std::collections::HashMap<String, HashSet<BrilInstruction>>
    ) -> HashSet<BrilInstruction> {
        // Find all predecessors and merge their out sets
        let mut merge = HashSet::new();
        
        // Find predecessors by looking through all edges
        for (pred_name, successors) in &cfg.edges {
            if successors.contains(&_block_name.to_string()) {
                if let Some(pred_out) = out_sets.get(pred_name) {
                    merge.extend(pred_out.iter().cloned());
                }
            }
        }
        
        merge
    }

    pub fn print_dataflow_results(
        &self, 
        function_name: &str, 
        in_sets: &HashMap<String, HashSet<BrilInstruction>>, 
        out_sets: &HashMap<String, HashSet<BrilInstruction>>
    ) {
        println!("\nDataFlow ConstProp analysis for function '{}'", function_name);
        println!("---------------------------------------------");
        
        // Get all block names and sort them for consistent output
        let mut block_names: Vec<&String> = in_sets.keys().collect();
        block_names.sort();
        
        for block_name in block_names {
            println!("\n Block: {}", block_name);
            println!("   ┌─ IN:");
            
            if let Some(in_set) = in_sets.get(block_name) {
                if in_set.is_empty() {
                    println!("   │    ∅ (empty)");
                } else {
                    // Sort instructions by destination name
                    let mut sorted_instrs: Vec<_> = in_set.iter().collect();
                    sorted_instrs.sort_by_key(|instr| instr.get_dest().unwrap_or(""));
                    
                    for instr in sorted_instrs {
                        if let (Some(dest), Some(op)) = (instr.get_dest(), instr.get_op()) {
                            let value = instr._get("value")
                                .map(|v| format!("{}", v))
                                .unwrap_or_else(|| "calculated".to_string());
                            println!("   │    {} = {} ({})", dest, value, op);
                        }
                    }
                }
            }
            
            println!("   └─ OUT:");
            if let Some(out_set) = out_sets.get(block_name) {
                if out_set.is_empty() {
                    println!("        ∅");
                } else {
                    // Sort instructions by destination name
                    let mut sorted_instrs: Vec<_> = out_set.iter().collect();
                    sorted_instrs.sort_by_key(|instr| instr.get_dest().unwrap_or(""));
                    
                    for instr in sorted_instrs {
                        if let (Some(dest), Some(op)) = (instr.get_dest(), instr.get_op()) {
                            let value = instr._get("value")
                                .map(|v| format!("{}", v))
                                .unwrap_or_else(|| "calculated".to_string());
                            println!("        {} = {} ({})", dest, value, op);
                        }
                    }
                }
            }
        }
    }
}

impl Pass for DataFlow {
    fn apply (&self, function: &mut FunctionAST) {
        let args = function.bril_function.get_args();
        let (in_sets, out_sets) = self.worklist(&mut function.cfg, args);
        
        // Pretty print the results
        self.print_dataflow_results(&function.name, &in_sets, &out_sets);
    }
}