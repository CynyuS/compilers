use crate::bril_parse::BrilProgram;
use crate::cfg::ControlFlowGraph;

pub trait Pass {
    fn apply(&self, function: &mut FunctionAST);
}

#[derive(Debug)]
pub struct ProgramAST {
    pub functions: Vec<FunctionAST>,
}

#[derive(Debug)]
pub struct FunctionAST {
    pub name: String,
    pub cfg: ControlFlowGraph,
    pub bril_function: crate::bril_parse::BrilFunction,
}

impl ProgramAST {
    pub fn from_bril_program(bril_program: BrilProgram) -> Self {
        let mut functions = Vec::new();
        
        for bril_function in bril_program.functions {
            let cfg = ControlFlowGraph::from_bril_function(&bril_function);
            let name = bril_function.name.clone();
            functions.push(FunctionAST {
                name,
                cfg,
                bril_function,
            });
        }

        ProgramAST { functions }
    }

    pub fn apply_pass(&mut self, pass: Box<dyn Pass>) {
        for function in &mut self.functions {
            pass.apply(function);
        }
    }
}