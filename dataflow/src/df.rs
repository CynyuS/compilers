use std::collections::{HashSet, HashMap, VecDeque};
use crate::ast::{Pass, FunctionAST};
use crate::basic_block::BasicBlock;

/// Answer the question: which variables have statically knowable constant values?

pub struct DataFlow;

#[derive(Debug, Clone, Eq, Hash, PartialEq)]
pub enum State {
    Undef,
    Const(i64),  // Store actual integer value
    NAC,         // Not A Constant
}

impl State {
    /// Meet operation for lattice join
    pub fn meet(&self, other: &State) -> State {
        match (self, other) {
            // If one is undef, return the other
            (State::Undef, other) => other.clone(),
            (self_state, State::Undef) => self_state.clone(),
            
            // If both are constants with same value, propagate that constant
            (State::Const(val1), State::Const(val2)) if val1 == val2 => State::Const(*val1),
            
            // If both are constants but different values, result is NAC
            (State::Const(_), State::Const(_)) => State::NAC,
            
            // If either is NAC, result is NAC
            (State::NAC, _) | (_, State::NAC) => State::NAC,
        }
    }
}

impl DataFlow {
    pub fn new() -> Self {
        DataFlow
    }

    /// `worklist` implements the fixed point iteration to convergence for constant propogation
    /// while also implementing preliminary constant folding.
    /// I consider `args` to not be defined at compile time, so it's initial values will be UNDEF
    pub fn worklist(&self, 
        cfg: &mut crate::cfg::ControlFlowGraph, 
        args: Option<&Vec<crate::bril_parse::BrilArg>>
    ) -> (HashMap<String, HashMap<String, State>>, HashMap<String, HashMap<String, State>>) {
        // Initialize in[*] and out[*] for all blocks
        // Each block maps variable names to their constant states
        let mut in_sets: HashMap<String, HashMap<String, State>> = HashMap::new();
        let mut out_sets: HashMap<String, HashMap<String, State>> = HashMap::new();
        
        // Initialize worklist with all blocks
        let mut worklist: VecDeque<String> = VecDeque::new();
        
        // Initialize each block's IN and OUT sets
        for block_name in cfg.blocks.keys() {
            // Initialize with empty map
            let mut initial_map = HashMap::new();
            
            // If this is the entry block, add function arguments as undefined initially
            if cfg.entry_block.as_ref() == Some(block_name) {
                if let Some(function_args) = args {
                    for arg in function_args {
                        // Function arguments start as undefined (not compile-time constants)
                        initial_map.insert(arg.name.clone(), State::Undef);
                    }
                }
            }

            in_sets.insert(block_name.clone(), initial_map);
            out_sets.insert(block_name.clone(), HashMap::new());
            worklist.push_back(block_name.clone());
        }
        
        // Fixed point dataflow analysis
        while let Some(block_name) = worklist.pop_front() {
            // in[b] = merge(out[p] for every predecessor p of b)
            let merged_in = if cfg.entry_block.as_ref() == Some(&block_name) {
                // Entry block: use initialized IN set
                in_sets.get(&block_name).cloned().unwrap_or_default()
            } else {
                // Non-entry block: merge predecessors' OUT sets
                let mut predecessor_sets: Vec<&HashMap<String, State>> = Vec::new();
                
                // Find predecessors by looking through all edges
                for (pred_name, successors) in &cfg.edges {
                    if successors.contains(&block_name) {
                        if let Some(pred_out) = out_sets.get(pred_name) {
                            predecessor_sets.push(pred_out);
                        }
                    }
                }
                self.merge(&predecessor_sets)
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
                        worklist.push_back(successor.clone());
                    }
                }
            }
            
            in_sets.insert(block_name.clone(), merged_in);
            out_sets.insert(block_name.clone(), new_out);
        }
        
        (in_sets, out_sets)
    }

    pub fn transfer(&self, block: &BasicBlock, in_vars: &HashMap<String, State>) -> HashMap<String, State> {
        let mut out_vars = in_vars.clone();
        
        for instr in &block.instructions {
            if let Some(dest) = instr.get_dest() {
                let new_state = match instr.get_op() {
                    Some("const") => {
                        // Parse constant value - handle both string and integer literals
                        if let Some(val_str) = instr.get_val() {
                            if let Ok(val) = val_str.parse::<i64>() {
                                State::Const(val)
                            } else {
                                State::NAC // Non-integer constants are NAC
                            }
                        } else if let Some(val_json) = instr._get("value") {
                            // Handle JSON number values
                            if let Some(val_int) = val_json.as_i64() {
                                State::Const(val_int)
                            } else {
                                State::NAC
                            }
                        } else {
                            State::NAC
                        }
                    },
                    
                    Some("id") => {
                        // Identity operation: propagate the state of the argument
                        if let Some(args) = instr.get_args() {
                            if args.len() == 1 {
                                out_vars.get(&args[0]).cloned().unwrap_or(State::Undef)
                            } else {
                                State::NAC
                            }
                        } else {
                            State::NAC
                        }
                    },
                    
                    Some(op) if self.is_foldable_operation(op) => {
                        // Check if this is an assignment with destination and integer type
                        let has_int_type = instr._get("type")
                            .and_then(|t| t.as_str())
                            .map(|t| t == "int")
                            .unwrap_or(false);
                            
                        if has_int_type {
                            if let Some(args) = instr.get_args() {
                                // Check if all arguments are constants
                                let arg_states: Vec<State> = args.iter()
                                    .map(|arg| out_vars.get(arg).cloned().unwrap_or(State::Undef))
                                    .collect();
                                
                                if arg_states.iter().all(|state| matches!(state, State::Const(_))) {
                                    // All arguments are constants, try to fold
                                    self.fold_operation(op, &arg_states)
                                } else if arg_states.iter().any(|state| matches!(state, State::NAC)) {
                                    State::NAC
                                } else {
                                    State::NAC // Some args are undefined or not a constant or mixed
                                }
                            } else {
                                State::NAC
                            }
                        } else {
                            State::NAC // Not a constant operation
                        }
                    },
                    
                    _ => State::NAC // Unknown operation
                };
                
                out_vars.insert(dest.to_string(), new_state);
            }
        }
        
        out_vars
    }

    /// Check if an operation can be constant-folded
    fn is_foldable_operation(&self, op: &str) -> bool {
        matches!(op, "add" | "sub" | "mul" | "div" | "mod" | "eq" | "lt" | "gt" | "le" | "ge" | "ne")
    }

    /// Perform constant folding for binary operations
    fn fold_operation(&self, op: &str, args: &[State]) -> State {
        if args.len() != 2 {
            return State::NAC;
        }
        
        match (&args[0], &args[1]) {
            (State::Const(a), State::Const(b)) => {
                match op {
                    "add" => State::Const(a + b),
                    "sub" => State::Const(a - b),  
                    "mul" => State::Const(a * b),
                    "div" => if *b != 0 { State::Const(a / b) } else { State::NAC }, // make sure no div zero
                    "mod" => if *b != 0 { State::Const(a % b) } else { State::NAC }, // make sure no mod zero
                    "eq" => State::Const(if a == b { 1 } else { 0 }),
                    "lt" => State::Const(if a < b { 1 } else { 0 }),
                    "gt" => State::Const(if a > b { 1 } else { 0 }),
                    "le" => State::Const(if a <= b { 1 } else { 0 }),
                    "ge" => State::Const(if a >= b { 1 } else { 0 }),
                    "ne" => State::Const(if a != b { 1 } else { 0 }),
                    _ => State::NAC
                }
            },
            _ => State::NAC
        }
    }

    /// `merge` takes in `pred_sets` and merges them according to
    /// the lattice meet operation for each variable.
    pub fn merge(&self, pred_sets: &[&HashMap<String, State>]) -> HashMap<String, State> {
        if pred_sets.is_empty() {
            return HashMap::new();
        }
        
        // Collect all variables mentioned in any predecessor
        let mut all_vars = HashSet::new();
        for pred_set in pred_sets {
            for var_name in pred_set.keys() {
                all_vars.insert(var_name.clone());
            }
        }
        
        let mut result = HashMap::new();
        
        // For each variable, compute the meet of its states across all predecessors
        for var in all_vars {
            let mut current_state = State::Undef;
            
            for pred_set in pred_sets {
                let pred_state = pred_set.get(&var).cloned().unwrap_or(State::Undef);
                current_state = current_state.meet(&pred_state);
            }
            
            result.insert(var, current_state);
        }
        
        result
    }

    pub fn print_dataflow_results(
        &self, 
        function_name: &str, 
        in_sets: &HashMap<String, HashMap<String, State>>, 
        out_sets: &HashMap<String, HashMap<String, State>>
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
                    println!("   │    ∅");
                } else {
                    // Sort variables by name
                    let mut sorted_vars: Vec<_> = in_set.iter().collect();
                    sorted_vars.sort_by_key(|(var_name, _)| *var_name);
                    
                    for (var_name, state) in sorted_vars {
                        let state_str = match state {
                            State::Undef => "UNDEF".to_string(),
                            State::Const(val) => format!("{}", val),
                            State::NAC => "NAC".to_string(),
                        };
                        println!("   │    {} = {}", var_name, state_str);
                    }
                }
            }
            
            println!("   └─ OUT:");
            if let Some(out_set) = out_sets.get(block_name) {
                if out_set.is_empty() {
                    println!("        ∅");
                } else {
                    // Sort variables by name
                    let mut sorted_vars: Vec<_> = out_set.iter().collect();
                    sorted_vars.sort_by_key(|(var_name, _)| *var_name);
                    
                    for (var_name, state) in sorted_vars {
                        let state_str = match state {
                            State::Undef => "UNDEF".to_string(),
                            State::Const(val) => format!("{}", val),
                            State::NAC => "NAC".to_string(),
                        };
                        println!("        {} = {}", var_name, state_str);
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