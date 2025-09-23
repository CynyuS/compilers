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
}

impl ProgramAST {
    pub fn from_bril_program(bril_program: BrilProgram) -> Self {
        let mut functions = Vec::new();
        
        for bril_function in bril_program.functions {
            let cfg = ControlFlowGraph::from_bril_function(&bril_function);
            functions.push(FunctionAST {
                name: bril_function.name,
                cfg,
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