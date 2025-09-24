import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'utils')))

from ai_processor import summarize_contract

sample_text = """
This contract states that Party A will deliver goods to Party B within 30 days.
Payment terms are net 30. Delays incur a penalty of 5% per week. 
The contract can be terminated with 15 days notice. Renewal is possible by mutual consent.
"""

summary = summarize_contract(sample_text)
print("=== Contract Summary ===")
print(summary)

#its a test

