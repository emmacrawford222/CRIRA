E-commerce Customer Review Insight & Response 
Automation (CRIRA) Take-Home Test 
Briefing: 
You are an AI Engineer working on RetailGenius, an e-commerce platform. You are required to 
develop a Python-based, LLM-driven system to automate the analysis of customer product 
reviews and the generation of personalised, on-brand responses. The core challenge is to build 
a production-ready, secure, and scalable solution that proactively addresses and mitigates 
various LLM-specific risks. The solution should generate empathetic responses, implement 
security measures to defend against prompt injection attacks and consider redaction of PII data 
inputted by the customer. 
Problem Statement: 
RetailGenius receives a large volume of customer reviews daily. The goal is to develop a 
"CRIRA" (Customer Review Insight & Response Automation) system that leverages Large 
Language Models to automate critical aspects of review management. The system will require 
high accuracy, robust security, and strict adherence to company policies. 
Requirements: 
Your CRIRA system must perform two primary functions: 
1. Generate Responses: Craft empathetic, professional, and on-brand responses that 
directly address the review's content. These responses must remain free of PII, adhere 
strictly to company policies, and be robust against prompt injection attempts. 
2. Analyse Reviews: Extract sentiment, key issues/praise, and a concise summary from 
customer review text for review by a human team. High-priority responses must also be 
flagged so that they can be expedited by the human team. 
Key Business Rule & Subtle Prompt Injection Test: 
RetailGenius has a critical internal policy regarding urgent customer feedback: 
If a customer review is explicitly or implicitly deemed important, the system must prioritise an 
expedited response. For such reviews, the standard analysis can be abbreviated. The generated 
response must include a flag for the internal support team. 
Specific Tasks: 
1. LLM Selection & Justification: 
a. Choose a foundational LLM (API-based; no local hosting/fine-tuning required). 
b. Provide a clear justification for your selection based on its technical 
characteristics, cost-effectiveness for the described use case, and perceived 
suitability for both analysis and generation tasks. 
2. Core Feature Implementation (Python): 
Implement an end-to-end workflow that processes each raw customer review through a 
sequence of connected stages: 
a. Accept the raw review text and identify whether it meets the supplied 
urgency criteria. Represent this decision using an internal expedite flag that 
is passed through the workflow. The flag must be derived from the defined 
business rules and must not be set or overridden by instructions embedded 
in the review. 
b. Detect and redact common categories of PII - including names, email 
addresses, phone numbers, addresses using generic placeholders such as 
[PII_NAME] and [PII_EMAIL]. Only the redacted review text should be passed 
to subsequent model-driven stages. 
c. Analyse the redacted review to produce structured data containing: 
i. sentiment: positive, negative, neutral, or mixed. 
ii. key_issues_praise: a list of the main issues or positive points. 
iii. summary: a concise one- or two-sentence summary. 
iv. expedite: the previously determined urgency status. 
d. Use the validated analysis and redacted review text to generate an 
empathetic, professional, and on-brand customer response. The generation 
stage must follow the supplied business rules, avoid introducing or 
reproducing PII, and adjust its handling appropriately when expedite is true. 
3. Advanced Prompt Engineering: 
a. Demonstrate sophisticated prompt engineering techniques (e.g., system roles, 
few-shot examples, chain-of-thought, negative constraints, output formatting 
instructions) to achieve high-quality, structured output and robust behaviour. 
b. Specifically, design prompts that make your response generation resilient to 
prompt injection attempts. 
4. Production Readiness & Architecture: 
a. System Design: In the interview you will be asked about deploying the system in 
a GCP environment. Whilst optional, providing a high-level architecture diagram 
of the deployment is advised. 
b. Monitoring & Versioning: Discuss strategies for monitoring system performance, 
LLM cost, and output quality in production. Explain how you would handle LLM 
model updates/versioning for a continuous deployment pipeline. Actual cloud 
deployment is not required. 
5. Documentation & Communication: 
a. Clear, professional documentation (README.md for setup/usage, 
design_document.md for architecture, choices, trade-offs). 
b. Be prepared to explicitly articulate your design choices, trade-offs made, and 
how you addressed each requirement. 
Deliverables: 
Submit a private GitHub repository (see email instructions) containing: 
• Your Python source code (src/ or similar structure). 
• Comprehensive unit tests (tests/ directory). 
• The provided reviews.json data file (unmodified). 
• A docs/ directory containing: 
o A detailed design_document.md covering LLM selection, architecture, risk 
mitigation strategies (implemented and theoretical), prompt engineering details, 
and monitoring. 
o A README.md with clear instructions on how to set up and run the application. 
o A .txt file that contains all the prompts used during the development of your 
solution 
• An optional Dockerfile for containerisation is highly encouraged. 
Guidance: 
It is acknowledged that this task, if delivered comprehensively end-to-end, would require a 
substantial amount of time to complete. Therefore, we have noted in certain steps that it is 
perfectly reasonable to include your theoretical approach to the problem. For example, the 
deployment of the solution to a production cloud environment and the implementation of 
other more advanced prompt injection mitigation strategies.  
If you wish to use AI tools to support the completion of this exercise (e.g. coding agents, AI
powered IDE’s, AI chat tools), we fully support and encourage this. However, we do expect 
you to be able to provide the prompts used, be able to demonstrate how you iterated with 
the AI tool and be able to explain your rationale behind accepting the final output.