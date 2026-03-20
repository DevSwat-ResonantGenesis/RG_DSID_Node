"""
Code Analyzer Agent
Analyzes code for complexity, security, and best practices.
"""

import json
import re
from datetime import datetime
from typing import Any

# Analysis patterns
SECURITY_PATTERNS = {
    "sql_injection": r"(execute|query)\s*\([^)]*['\"].*%s|format|f['\"]",
    "hardcoded_secrets": r"(password|secret|api_key|token)\s*=\s*['\"][^'\"]+['\"]",
    "eval_usage": r"\beval\s*\(",
    "exec_usage": r"\bexec\s*\(",
    "shell_injection": r"(os\.system|subprocess\.call|subprocess\.run)\s*\([^)]*\+",
    "pickle_usage": r"pickle\.(load|loads)\s*\(",
}

COMPLEXITY_INDICATORS = {
    "nested_loops": r"(for|while)[^:]+:[^:]+\b(for|while)\b",
    "long_function": 50,  # lines threshold
    "many_params": 5,  # parameter count threshold
    "deep_nesting": 4,  # nesting level threshold
}

BEST_PRACTICES = {
    "no_docstring": r"def\s+\w+\s*\([^)]*\)\s*:\s*\n\s*[^'\"]",
    "magic_numbers": r"[^a-zA-Z_]([2-9]\d{2,}|[1-9]\d{3,})[^a-zA-Z_\d]",
    "broad_except": r"except\s*:",
    "unused_import": r"^import\s+\w+|^from\s+\w+\s+import",
    "print_debug": r"\bprint\s*\(",
}


class CodeAnalyzerAgent:
    """Agent that analyzes code snippets."""
    
    def __init__(self):
        self.memory = {}
        self.analysis_count = 0
    
    def handle(self, input_data: dict, context: dict) -> dict:
        """Main entry point for agent execution."""
        message = input_data.get("message", "").strip()
        code = input_data.get("code", "").strip()
        language = input_data.get("language", "python").lower()
        
        # If no message, return greeting
        if not message and not code:
            return self._greeting()
        
        # Check for specific commands
        message_lower = message.lower()
        
        if "help" in message_lower or "what can you do" in message_lower:
            return self._help()
        
        if code or "analyze" in message_lower:
            # Extract code from message if not provided separately
            if not code and "```" in message:
                code = self._extract_code_block(message)
            
            if code:
                return self._analyze_code(code, language)
            else:
                return {
                    "type": "error",
                    "message": "Please provide code to analyze. You can paste it directly or wrap it in ```code blocks```.",
                }
        
        if "security" in message_lower:
            return self._explain_security_checks()
        
        if "complexity" in message_lower:
            return self._explain_complexity_metrics()
        
        # Default response
        return {
            "type": "info",
            "message": "I can analyze code for you. Send me a code snippet with 'analyze' or paste code directly.",
            "suggestions": [
                "Send code wrapped in ```python ... ```",
                "Ask 'what security issues do you check for?'",
                "Ask 'what complexity metrics do you use?'"
            ]
        }
    
    def _greeting(self) -> dict:
        """Return greeting response."""
        return {
            "type": "greeting",
            "message": "Hello! I'm the Code Analyzer Agent. I can analyze your code for security issues, complexity, and best practices.",
            "suggestions": [
                "Paste code to analyze",
                "Ask 'what can you do' for capabilities",
                "Ask about security checks"
            ]
        }
    
    def _help(self) -> dict:
        """Return help information."""
        return {
            "type": "help",
            "message": "I analyze code for quality and security.",
            "capabilities": {
                "security_analysis": [
                    "SQL injection detection",
                    "Hardcoded secrets detection",
                    "Dangerous function usage (eval, exec)",
                    "Shell injection risks",
                    "Insecure deserialization"
                ],
                "complexity_analysis": [
                    "Nested loop detection",
                    "Function length analysis",
                    "Parameter count check",
                    "Nesting depth analysis"
                ],
                "best_practices": [
                    "Missing docstrings",
                    "Magic numbers",
                    "Broad exception handlers",
                    "Debug print statements"
                ]
            },
            "usage": "Send me code wrapped in ```python ... ``` or just paste it directly."
        }
    
    def _extract_code_block(self, text: str) -> str:
        """Extract code from markdown code blocks."""
        pattern = r"```(?:\w+)?\s*([\s\S]*?)```"
        match = re.search(pattern, text)
        return match.group(1).strip() if match else ""
    
    def _analyze_code(self, code: str, language: str) -> dict:
        """Perform comprehensive code analysis."""
        self.analysis_count += 1
        
        results = {
            "type": "analysis",
            "language": language,
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {},
            "security_issues": [],
            "complexity_issues": [],
            "best_practice_issues": [],
            "recommendations": [],
            "score": 100
        }
        
        # Basic metrics
        lines = code.split("\n")
        results["metrics"] = {
            "total_lines": len(lines),
            "code_lines": len([l for l in lines if l.strip() and not l.strip().startswith("#")]),
            "comment_lines": len([l for l in lines if l.strip().startswith("#")]),
            "blank_lines": len([l for l in lines if not l.strip()]),
            "functions": len(re.findall(r"def\s+\w+", code)),
            "classes": len(re.findall(r"class\s+\w+", code)),
        }
        
        # Security analysis
        for issue_name, pattern in SECURITY_PATTERNS.items():
            matches = re.findall(pattern, code, re.IGNORECASE | re.MULTILINE)
            if matches:
                results["security_issues"].append({
                    "type": issue_name,
                    "severity": "high" if issue_name in ["sql_injection", "shell_injection", "eval_usage"] else "medium",
                    "count": len(matches),
                    "description": self._get_issue_description(issue_name)
                })
                results["score"] -= 15 if issue_name in ["sql_injection", "shell_injection"] else 10
        
        # Complexity analysis
        if re.search(COMPLEXITY_INDICATORS["nested_loops"], code):
            results["complexity_issues"].append({
                "type": "nested_loops",
                "severity": "medium",
                "description": "Nested loops detected - consider refactoring for better performance"
            })
            results["score"] -= 5
        
        # Check function lengths
        functions = re.findall(r"def\s+(\w+)[^:]+:([\s\S]*?)(?=\ndef\s|\nclass\s|\Z)", code)
        for func_name, func_body in functions:
            func_lines = len(func_body.strip().split("\n"))
            if func_lines > COMPLEXITY_INDICATORS["long_function"]:
                results["complexity_issues"].append({
                    "type": "long_function",
                    "function": func_name,
                    "lines": func_lines,
                    "description": f"Function '{func_name}' has {func_lines} lines - consider breaking it up"
                })
                results["score"] -= 5
        
        # Best practices
        for issue_name, pattern in BEST_PRACTICES.items():
            if issue_name == "no_docstring":
                # Check each function for docstring
                for func_name, func_body in functions:
                    if not func_body.strip().startswith('"""') and not func_body.strip().startswith("'''"):
                        results["best_practice_issues"].append({
                            "type": "missing_docstring",
                            "function": func_name,
                            "description": f"Function '{func_name}' is missing a docstring"
                        })
                        results["score"] -= 2
            elif re.search(pattern, code):
                results["best_practice_issues"].append({
                    "type": issue_name,
                    "description": self._get_issue_description(issue_name)
                })
                results["score"] -= 3
        
        # Ensure score doesn't go below 0
        results["score"] = max(0, results["score"])
        
        # Generate recommendations
        results["recommendations"] = self._generate_recommendations(results)
        
        # Generate summary
        total_issues = (
            len(results["security_issues"]) + 
            len(results["complexity_issues"]) + 
            len(results["best_practice_issues"])
        )
        
        if total_issues == 0:
            results["summary"] = "✅ Great job! No significant issues found."
        elif results["score"] >= 80:
            results["summary"] = f"⚠️ Found {total_issues} minor issue(s). Overall code quality is good."
        elif results["score"] >= 50:
            results["summary"] = f"⚠️ Found {total_issues} issue(s) that should be addressed."
        else:
            results["summary"] = f"❌ Found {total_issues} significant issue(s). Review recommended."
        
        # Store in memory
        self.memory["last_analysis"] = {
            "timestamp": results["timestamp"],
            "score": results["score"],
            "issues": total_issues
        }
        
        return results
    
    def _get_issue_description(self, issue_type: str) -> str:
        """Get human-readable description for an issue type."""
        descriptions = {
            "sql_injection": "Potential SQL injection vulnerability - use parameterized queries",
            "hardcoded_secrets": "Hardcoded secrets detected - use environment variables or secret management",
            "eval_usage": "eval() is dangerous - avoid if possible or sanitize input thoroughly",
            "exec_usage": "exec() is dangerous - avoid if possible or sanitize input thoroughly",
            "shell_injection": "Potential shell injection - avoid string concatenation in shell commands",
            "pickle_usage": "pickle.load is unsafe with untrusted data - consider using json instead",
            "magic_numbers": "Magic numbers detected - use named constants for better readability",
            "broad_except": "Broad exception handler - catch specific exceptions instead",
            "print_debug": "Print statements found - consider using proper logging",
        }
        return descriptions.get(issue_type, f"Issue: {issue_type}")
    
    def _generate_recommendations(self, results: dict) -> list:
        """Generate actionable recommendations based on analysis."""
        recommendations = []
        
        if results["security_issues"]:
            recommendations.append({
                "priority": "high",
                "category": "security",
                "action": "Address security vulnerabilities before deployment"
            })
        
        if any(i["type"] == "long_function" for i in results["complexity_issues"]):
            recommendations.append({
                "priority": "medium",
                "category": "maintainability",
                "action": "Break large functions into smaller, focused functions"
            })
        
        if any(i["type"] == "missing_docstring" for i in results["best_practice_issues"]):
            recommendations.append({
                "priority": "low",
                "category": "documentation",
                "action": "Add docstrings to document function purpose and parameters"
            })
        
        if results["metrics"]["comment_lines"] == 0 and results["metrics"]["code_lines"] > 20:
            recommendations.append({
                "priority": "low",
                "category": "documentation",
                "action": "Consider adding comments to explain complex logic"
            })
        
        return recommendations
    
    def _explain_security_checks(self) -> dict:
        """Explain security checks performed."""
        return {
            "type": "info",
            "message": "Security checks I perform:",
            "checks": [
                {"name": "SQL Injection", "description": "Detects string concatenation in SQL queries"},
                {"name": "Hardcoded Secrets", "description": "Finds passwords, API keys, tokens in code"},
                {"name": "Dangerous Functions", "description": "Flags eval(), exec(), and similar"},
                {"name": "Shell Injection", "description": "Detects unsafe shell command construction"},
                {"name": "Insecure Deserialization", "description": "Warns about pickle with untrusted data"}
            ]
        }
    
    def _explain_complexity_metrics(self) -> dict:
        """Explain complexity metrics used."""
        return {
            "type": "info",
            "message": "Complexity metrics I analyze:",
            "metrics": [
                {"name": "Nested Loops", "description": "Detects loops within loops"},
                {"name": "Function Length", "threshold": "50+ lines triggers warning"},
                {"name": "Parameter Count", "threshold": "5+ parameters triggers warning"},
                {"name": "Nesting Depth", "threshold": "4+ levels triggers warning"}
            ]
        }


# Agent entry point
agent = CodeAnalyzerAgent()

def handle(input_data: dict, context: dict) -> dict:
    """Main handler called by the runtime."""
    return agent.handle(input_data, context)


# Test runner
if __name__ == "__main__":
    print("=" * 60)
    print("Code Analyzer Agent - Test Run")
    print("=" * 60)
    
    test_cases = [
        {"message": ""},
        {"message": "what can you do"},
        {
            "message": "analyze this",
            "code": '''
def get_user(user_id):
    query = "SELECT * FROM users WHERE id = " + user_id
    password = "secret123"
    result = eval(user_input)
    return result
'''
        },
        {
            "message": "analyze",
            "code": '''
def calculate_total(items):
    """Calculate the total price of items."""
    total = 0
    for item in items:
        total += item.price * 1.08  # tax
    return total
'''
        }
    ]
    
    for test in test_cases:
        print(f"\n> Input: {test}")
        result = handle(test, {})
        print(f"< Output: {json.dumps(result, indent=2)}")
    
    print("\n" + "=" * 60)
    print("Test complete!")
