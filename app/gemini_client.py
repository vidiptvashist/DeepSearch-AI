# app/gemini_client.py
from google import genai
from google.genai import types
import os
import logging
import re
from google.genai.errors import APIError
import dotenv
import json

dotenv.load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# --- Helpers ---
def _sanitize_display_name(display_name: str) -> str:
    return re.sub(r"[^\w\-\.]", "_", display_name)

def _user_display_prefix(user_id: str) -> str:
    return f"usr-{user_id}__"

def _user_store_display(user_id: str, display_name: str) -> str:
    safe = _sanitize_display_name(display_name)
    return f"{_user_display_prefix(user_id)}{safe}"

def _find_store_resource_by_display_prefix(prefix: str) -> str | None:
    try:
        stores = client.file_search_stores.list()
        for s in stores:
            dn = getattr(s, "display_name", None)
            if dn and dn.startswith(prefix):
                return s.name
    except Exception:
        pass
    return None

# --- Store Management ---
def create_file_search_store_for_user(user_id: str, display_name: str):
    user_display = _user_store_display(user_id, display_name)
    try:
        store = client.file_search_stores.create(config={"display_name": user_display})
        return {"resource_name": store.name, "display_name": store.display_name}
    except APIError as e:
        logger.error("Create Store Failed: %s", e)
        raise

def delete_store_for_user(user_id: str, display_name: str):
    prefix = _user_display_prefix(user_id)
    search_prefix = display_name if display_name.startswith(prefix) else _user_store_display(user_id, display_name)
    store_resource = _find_store_resource_by_display_prefix(search_prefix)
    if store_resource:
        client.file_search_stores.delete(name=store_resource, config={"force": True})

def list_file_search_stores_for_user(user_id: str) -> list:
    prefix = _user_display_prefix(user_id)
    try:
        stores = client.file_search_stores.list()
        return [{"resource_name": s.name, "display_name": s.display_name} for s in stores if getattr(s, "display_name", "").startswith(prefix)]
    except Exception:
        return []

# --- Document Management ---
def upload_file_to_store_for_user(user_id: str, display_name: str, file_path: str, original_name: str):
    prefix = _user_display_prefix(user_id)
    search_prefix = display_name if display_name.startswith(prefix) else _user_store_display(user_id, display_name)
    store_resource = _find_store_resource_by_display_prefix(search_prefix)
    if not store_resource: raise ValueError("Store not found")

    client.file_search_stores.upload_to_file_search_store(
        file=file_path,
        file_search_store_name=store_resource,
        config={"chunking_config": {"white_space_config": {"max_tokens_per_chunk": 512, "max_overlap_tokens": 51}}, 'display_name': original_name},
    )
    return {"ok": True}

def list_documents_in_store_for_user(user_id: str, display_name: str) -> list:
    prefix = _user_display_prefix(user_id)
    search_prefix = display_name if display_name.startswith(prefix) else _user_store_display(user_id, display_name)
    store_resource = _find_store_resource_by_display_prefix(search_prefix)
    if not store_resource: return []

    try:
        documents = client.file_search_stores.documents.list(parent=store_resource)
        return [{"resource_name": getattr(d, "name", None), "display_name": getattr(d, "display_name", "Untitled"), "mime_type": getattr(d, "mime_type", "application/octet-stream")} for d in documents]
    except Exception:
        return []

def delete_document_from_store_for_user(user_id: str, display_name: str, document_resource_name: str):
    client.file_search_stores.documents.delete(name=document_resource_name, config={"force": True})
    return {"ok": True}

# --- Chat Logic ---


system_prompt = """
# System Prompt: Technical Chemistry Manufacturing Analysis


## Role and Expertise Level
You are an expert technical analyst specializing in chemistry and chemical manufacturing processes.
Your name is DeepSearch AI developed as POC by Vidipt Vashist, 
Your audience consists of subject matter experts with PhD-level knowledge in chemistry, chemical engineering, and related fields. They operate manufacturing facilities and are deeply familiar with:
- Advanced synthetic chemistry and reaction mechanisms
- Process chemistry and scale-up considerations
- Chemical engineering principles
- Manufacturing constraints and optimization
- Regulatory and safety requirements
- Intellectual property landscape

## Primary Objective
Your core mission is to **generate novel insights** from technical documents, particularly patents and technical literature. You must go beyond summarization to identify:
- Non-obvious connections between disclosed technologies
- Potential process improvements or alternative approaches
- Gaps in prior art that suggest innovation opportunities
- Hidden implications of specific process parameters or conditions
- Cross-domain applications of disclosed methodologies

## Document Types You Analyze
- **Patents**: Claims, specifications, examples, and prior art citations
- **Technical papers**: Peer-reviewed research, conference proceedings
- **Process documentation**: Manufacturing procedures, batch records
- **Regulatory filings**: FDA submissions, safety data sheets
- **Analytical reports**: Characterization data, quality control documents

## Response Standards

### Technical Depth
- **Assume advanced knowledge**: Skip basic explanations unless specifically requested
- **Use precise nomenclature**: IUPAC naming, standardized abbreviations, technical terminology
- **Include quantitative details**: Specific temperatures, pressures, yields, concentrations, reaction times
- **Reference analytical methods**: Specify techniques (HPLC, NMR, GC-MS, XRD, etc.) when discussing characterization
- **Discuss mechanism**: Explain reaction pathways, intermediates, and rate-determining steps when relevant

### Insight Generation Framework
When analyzing documents, systematically consider:

1. **Process Optimization Angles**
   - Alternative reagents or catalysts that might improve selectivity/yield
   - Process intensification opportunities (continuous flow, microwave, etc.)
   - Energy efficiency improvements
   - Waste reduction strategies
   - Scale-up considerations not explicitly addressed

2. **Competitive Intelligence**
   - How does this compare to existing commercial processes?
   - What are the cost implications of disclosed methods?
   - Patent claim scope and potential workarounds
   - Freedom-to-operate considerations

3. **Hidden Dependencies**
   - Critical parameters that aren't emphasized but control outcomes
   - Equipment requirements implied but not stated
   - Raw material specifications that impact reproducibility
   - Sequence-dependent operations

4. **Cross-Functional Applications**
   - Could this chemistry apply to adjacent product lines?
   - Are there platform technology implications?
   - Potential for process transfer across facilities

5. **Risk and Constraint Analysis**
   - Safety concerns (exotherms, hazardous intermediates, etc.)
   - Regulatory hurdles for implementation
   - Supply chain vulnerabilities
   - Analytical method limitations

### Response Structure
Organize responses as follows:

**1. Key Technical Findings**
- Distill the core chemistry, process, or methodology
- Highlight critical parameters and their ranges
- Note any surprising or unexpected results

**2. Novel Insights**
- Present non-obvious observations
- Make connections to broader literature or adjacent technologies
- Identify what's *not* said but implied
- Suggest testable hypotheses for improvement

**3. Manufacturing Implications**
- Discuss practical implementation considerations
- Address scalability, economics, and operational complexity
- Compare to existing manufacturing practices

**4. Strategic Considerations**
- IP positioning and potential gaps
- Competitive advantages or disadvantages
- Innovation opportunities revealed by this analysis

**5. Recommended Actions** (when appropriate)
- Experimental validation priorities
- Further literature or patent searches needed
- Technical questions requiring clarification

## Analytical Rigor
- **Cite specific sections**: Reference claim numbers, example numbers, paragraph locations
- **Distinguish fact from interpretation**: Be clear when you're inferring vs. reporting disclosed information
- **Acknowledge limitations**: Note where data is insufficient or ambiguous
- **Quantify uncertainty**: Use phrases like "likely," "suggests," "possibly" appropriately
- **Challenge assumptions**: Question whether disclosed results are reproducible or optimized

## Communication Style
- **Concise but comprehensive**: Dense information without unnecessary words
- **Logical flow**: Structure arguments clearly with supporting evidence
- **Technical precision**: Avoid vague language; be specific
- **Actionable**: Focus on what can be done with the information
- **Intellectually honest**: Admit when you don't know or when multiple interpretations exist

## What NOT to Do
- ❌ Don't oversimplify chemistry for a general audience
- ❌ Don't merely summarize without adding analytical value
- ❌ Don't ignore inconvenient data or negative results
- ❌ Don't make definitive claims beyond what evidence supports
- ❌ Don't overlook safety, environmental, or regulatory dimensions
- ❌ Don't provide generic insights that could apply to any document

## Example Insight Quality Levels

**Poor (Avoid)**
"This patent describes a new synthesis method that could be useful."

**Good (Target)**
"Claims 1-7 disclose a one-pot cascade using DBU as base (0.1-0.5 eq, Example 3) which eliminates the aqueous workup in prior art (US9876543). However, Example 7's 73% yield at 0.3 eq DBU suggests an optimum exists. The lack of kinetic data for the competing elimination pathway raises questions about reproducibility at scale where mixing is non-ideal. Testing 0.25-0.35 eq with inline HPLC monitoring could narrow the operational window. Additionally, the cited THF/DMSO co-solvent system (3:1 v/v) may pose solvent recovery challenges given the azeotrope formation; alternative polar aprotics warrant evaluation."

## Specialized Knowledge Areas
You have deep expertise in:
- Organic synthesis and medicinal chemistry
- Catalysis (homogeneous, heterogeneous, biocatalysis)
- Polymer chemistry and materials science
- Analytical chemistry and spectroscopy
- Process safety and chemical hazard assessment
- Chemical engineering unit operations
- Green chemistry principles
- Regulatory chemistry (ICH, FDA, EPA)
- Patent claim construction and infringement analysis

## When Uncertain
If you encounter information outside your knowledge base or require clarification:
- Explicitly state the limitation
- Explain what additional information would enable better analysis
- Suggest where to find authoritative information
- Don't speculate beyond reasonable technical inference

---

**Remember**: Your users are experts seeking your analytical capabilities to see what they might have missed. Add value through rigorous technical analysis, creative connections, and actionable insights—not through basic explanations.


# Output Format
1. Answer the question directly.
2. Do NOT manually add a "Sources" section in the text. Use the tool to cite.
3. At the very end, provide 3 follow-up questions in this block:
<<<SUGGESTIONS>>>
1. Question 1
2. Question 2
3. Question 3
"""


def query_in_store_for_user(user_id: str, display_name: str, query: str, history: list = None, custom_system_instruction: str = None) -> dict:
    prefix = _user_display_prefix(user_id)
    search_prefix = display_name if display_name.startswith(prefix) else _user_store_display(user_id, display_name)
    store_resource = _find_store_resource_by_display_prefix(search_prefix)
    if not store_resource: raise ValueError("Store not found")

    contents = []
    if history:
        for msg in history[-6:]:
            role = 'model' if msg.get("role") == 'assistant' else msg.get("role")
            if role in ['user', 'model']:
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg.get("content", ""))]))
    
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=query)]))

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=custom_system_instruction if custom_system_instruction else system_prompt,
            temperature=0.3,
            tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[store_resource]))]
        )
    )

    # 1. Extract Text & Suggestions
    full_text = getattr(response, "text", "") or ""
    suggestions = []
    if '<<<SUGGESTIONS>>>' in full_text:
        parts = full_text.split('<<<SUGGESTIONS>>>')
        full_text = parts[0].strip()
        suggestions = re.findall(r'\d+\.\s+(.*)', parts[1])

    # 2. Extract Citations
    citations = []
    try:
        for cand in getattr(response, "candidates", []) or []:
            for chunk in getattr(cand.grounding_metadata, "grounding_chunks", []) or []:
                title = getattr(chunk.retrieved_context, "title", "Unknown Source")
                uri = getattr(chunk.retrieved_context, "uri", "")
                text_preview = getattr(chunk.retrieved_context, "text", "")[:100] + "..."
                
                # Dedup based on title
                if not any(c['title'] == title for c in citations):
                    citations.append({"title": title, "uri": uri, "preview": text_preview})
    except Exception:
        pass

    return {
        "text": full_text,
        "citations": citations,
        "suggestions": suggestions
    }

def enhance_system_prompt(prompt: str) -> str:
    enhancement_prompt = f"""
    You are an expert prompt engineer. Refine the following system prompt to be more effective, clear, and robust for an AI assistant.
    Keep the intent but improve the instructions.
    
    Original Prompt:
    {prompt}
    
    Refined Prompt:
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=enhancement_prompt
        )
        return getattr(response, "text", "").strip()
    except Exception as e:
        logger.error("Enhance Prompt Failed: %s", e)
        return prompt

def generate_knowledge_graph(user_id: str, display_name: str) -> dict:
    docs = list_documents_in_store_for_user(user_id, display_name)
    if not docs: return {"nodes": [], "links": []}
    
    doc_list = "\n".join([f"- {d['display_name']}" for d in docs[:20]]) # Limit to 20 docs for summary analysis
    
    prompt = f"""
    Analyze the following list of documents in a knowledge base:
    {doc_list}
    
    Your goal is to create a dense and interconnected Knowledge Graph.
    
    Return a JSON object with two keys:
    1. "nodes": A list of objects {{ "id": "Short Label", "group": 1, "val": 10 }}. 
       - Group 1: Document Names (val: 20)
       - Group 2: Key Topics/Concepts (val: 10)
       - Group 3: Entities (People, Orgs, Locations) (val: 5)
    2. "links": A list of objects {{ "source": "id_of_source", "target": "id_of_target" }}.
       - Create MANY links. Connect documents to their topics.
       - Connect related topics to each other.
       - Connect documents that share similar topics.
       
    Keep labels short (max 3 words). Max 30 nodes. Max 50 links.
    Output purely JSON.
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(getattr(response, "text", "{}"))
    except Exception as e:
        logger.error("Graph Gen Failed: %s", e)
        return {"nodes": [], "links": []}