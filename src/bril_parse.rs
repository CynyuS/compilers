use std::fs;
use serde_json::Value;
use std::error::Error;
use std::fmt;

/// This module parses a bril program that is inputted in a json format into
/// functions, instructions, and returns a BrilProgram

#[derive(Debug, Clone)]
pub struct BrilProgram {
    pub functions: Vec<BrilFunction>,
}

#[derive(Debug, Clone)]
/// Bril functions have a `name` and are made up of a list of 
/// instructions. We won't need `name` until global basic block analysis
pub struct BrilFunction {
    #[allow(dead_code)]
    pub name: String, 
    pub instructions: Vec<BrilInstruction>,
}

#[derive(Debug, Clone)]
pub struct BrilInstruction {
    pub data: Value,
}

impl BrilInstruction {
    pub fn new(data: Value) -> Self {
        BrilInstruction { data }
    }

    /// For debug purposes
    pub fn _get(&self, key: &str) -> Option<&Value> {
        self.data.get(key)
    }

    pub fn has_label(&self) -> bool {
        self.data.get("label").is_some()
    }

    pub fn get_op(&self) -> Option<&str> {
        self.data.get("op").and_then(|v| v.as_str())
    }

    pub fn get_label(&self) -> Option<&str> {
        self.data.get("label").and_then(|v| v.as_str())
    }

    pub fn get_dest(&self) -> Option<&str> {
        self.data.get("dest").and_then(|v| v.as_str())
    }

    pub fn get_args(&self) -> Option<Vec<String>> {
        self.data.get("args")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(|s| s.to_string()))
                    .collect()
            })
    }

    pub fn get_labels(&self) -> Option<Vec<String>> {
        self.data.get("labels")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(|s| s.to_string()))
                    .collect()
            })
    }

    pub fn get_funcs(&self) -> Option<Vec<String>> {
        self.data.get("funcs")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(|s| s.to_string()))
                    .collect()
            })
    }
}

#[derive(Debug)]
pub enum BrilParseError {
    IoError(std::io::Error),
    JsonError(serde_json::Error),
    InvalidFormat(String),
}

impl fmt::Display for BrilParseError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            BrilParseError::IoError(e) => write!(f, "IO error: {}", e),
            BrilParseError::JsonError(e) => write!(f, "JSON error: {}", e),
            BrilParseError::InvalidFormat(msg) => write!(f, "Invalid format: {}", msg),
        }
    }
}

impl Error for BrilParseError {}

impl From<std::io::Error> for BrilParseError {
    fn from(error: std::io::Error) -> Self {
        BrilParseError::IoError(error)
    }
}

impl From<serde_json::Error> for BrilParseError {
    fn from(error: serde_json::Error) -> Self {
        BrilParseError::JsonError(error)
    }
}

pub struct BrilParser;

impl BrilParser {
    pub fn from_file(file_path: &str) -> Result<BrilProgram, BrilParseError> {
        let file_content = fs::read_to_string(file_path)?;
        Self::from_string(&file_content)
    }

    pub fn from_string(content: &str) -> Result<BrilProgram, BrilParseError> {
        let json_value: Value = serde_json::from_str(content)?;
        Self::from_json(json_value)
    }

    pub fn from_json(json: Value) -> Result<BrilProgram, BrilParseError> {
        let functions_json = json.get("functions")
            .and_then(|f| f.as_array())
            .ok_or_else(|| BrilParseError::InvalidFormat("Missing 'functions' array".to_string()))?;

        let mut functions = Vec::new();

        for func_json in functions_json {
            let name = func_json.get("name")
                .and_then(|n| n.as_str())
                .unwrap_or("unnamed")
                .to_string();

            let mut instructions = Vec::new();

            if let Some(instrs) = func_json.get("instrs").and_then(|i| i.as_array()) {
                for instr in instrs {
                    instructions.push(BrilInstruction::new(instr.clone()));
                }
            }

            functions.push(BrilFunction { name, instructions });
        }

        Ok(BrilProgram { functions })
    }
}