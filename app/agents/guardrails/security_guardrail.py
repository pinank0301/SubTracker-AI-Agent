import re
import logging
from typing import Tuple, List

logger = logging.getLogger(__name__)


class SecurityGuardrail:
    """
    Guardrail to detect and neutralize prompt injections, jailbreaks, and system overrides.
    """
    # Common jailbreak and prompt injection triggers
    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)",
        r"disregard\s+(all\s+)?(previous|prior|system)\s+directions",
        r"you\s+are\s+now\s+in\s+(developer|dan|jailbreak|unrestricted)\s+mode",
        r"reveal\s+(your\s+)?(system\s+prompt|hidden\s+instructions|secret\s+key)",
        r"print\s+(your\s+)?(system\s+prompt|initial\s+instructions)",
        r"pretend\s+you\s+have\s+no\s+(rules|guidelines|restrictions)",
        r"override\s+system\s+security",
        r"bypass\s+all\s+guardrails",
        r"give\s+me\s+the\s+api\s*key",
        r"dump\s+database",
        r"drop\s+table\s+",
        r"<script>.*?</script>"
    ]

    def __init__(self):
        self.compiled_patterns = [
            re.compile(p, re.IGNORECASE | re.DOTALL) for p in self.INJECTION_PATTERNS
        ]

    def validate_input(self, user_input: str) -> Tuple[bool, str, List[str]]:
        """
        Validates user input for malicious prompt injection attempts.
        Returns: (passed: bool, sanitized_input: str, flagged_reasons: List[str])
        """
        if not user_input or not user_input.strip():
            return False, "", ["Empty input message"]

        # Max length check to prevent DOS/overflow
        if len(user_input) > 4000:
            user_input = user_input[:4000]

        flags = []
        for pattern in self.compiled_patterns:
            if pattern.search(user_input):
                flags.append(f"Security Alert: Blocked pattern '{pattern.pattern}' detected")

        if flags:
            logger.warning("Security Guardrail triggered: %s for input: %s", flags, user_input[:100])
            return False, user_input, flags

        # Clean control characters
        sanitized = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", user_input).strip()
        return True, sanitized, []
