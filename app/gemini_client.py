# app/gemini_client.py
from google import genai
from google.genai import types
import os
import logging
import re
from google.genai.errors import APIError
import dotenv

dotenv.load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# --- helper: user-scoped store name ---
def _sanitize_display_name(display_name: str) -> str:
    # replace spaces and unsafe chars
    return re.sub(r"[^\w\-\.]", "_", display_name)

def _user_display_prefix(user_id: str) -> str:
    return f"usr-{user_id}__"

def _user_store_display(user_id: str, display_name: str) -> str:
    safe = _sanitize_display_name(display_name)
    return f"{_user_display_prefix(user_id)}{safe}"

def _find_store_resource_by_display_prefix(prefix: str) -> str | None:
    """
    Return the full resource name (e.g. fileSearchStores/...) whose display_name
    starts with the given prefix. Returns None if not found.
    """
    try:
        stores = client.file_search_stores.list()
    except Exception as e:
        logger.error("Failed listing file_search_stores: %s", e)
        raise

    for s in stores:
        dn = getattr(s, "display_name", None)
        # Some API objects may not expose display_name; guard defensively
        if dn and dn.startswith(prefix):
            return s.name
    return None


def create_file_search_store_for_user(user_id: str, display_name: str):
    """
    Create a new File Search Store with user-scoped display_name prefix.
    Returns a dict: {"resource_name": <full resource>, "display_name": <the display_name>}
    """
    # Build a user-scoped display_name so we can filter later.
    user_display = _user_store_display(user_id, display_name)
    try:
        store = client.file_search_stores.create(config={"display_name": user_display})
        logger.info("SUCCESS: Store created. resource_name=%s display_name=%s", store.name, store.display_name)
        return {"resource_name": store.name, "display_name": store.display_name}
    except APIError as e:
        logger.error("ERROR: Could not create File Search Store. Details: %s", e)
        raise


def delete_store_for_user(user_id: str, display_name: str):
    # Check if display_name already has the prefix (from frontend)
    prefix = _user_display_prefix(user_id)
    if display_name.startswith(prefix):
        search_prefix = display_name
    else:
        search_prefix = _user_store_display(user_id, display_name)
    
    store_resource = _find_store_resource_by_display_prefix(search_prefix)
    if not store_resource:
        raise ValueError(f"No store found matching display prefix: {prefix}")
    try:
        client.file_search_stores.delete(name=store_resource, config={"force": True})
        logger.info("SUCCESS: File Search Store %s deleted.", store_resource)
    except Exception as e:
        logger.error("ERROR: Could not delete store: %s", e)
        raise


def upload_file_to_store_for_user(user_id: str, display_name: str, file_path: str, original_name: str) -> dict:
    """
    Uploads file at file_path to the user's store. Returns {"ok": True, "store_resource": ..., "uploaded": True}
    """
    # Check if display_name already has the prefix (from frontend)
    prefix = _user_display_prefix(user_id)
    logger.info(f"Upload: user_id={user_id}, display_name={display_name}, prefix={prefix}")
    
    if display_name.startswith(prefix):
        search_prefix = display_name
        logger.info(f"Display name already has prefix, using: {search_prefix}")
    else:
        search_prefix = _user_store_display(user_id, display_name)
        logger.info(f"Adding prefix, using: {search_prefix}")
    
    store_resource = _find_store_resource_by_display_prefix(search_prefix)
    if not store_resource:
        raise ValueError(f"No store found matching display prefix: {search_prefix}")

    try:
        client.file_search_stores.upload_to_file_search_store(
            file=file_path,
            file_search_store_name=store_resource,
            config={
                "chunking_config": {
                    "white_space_config": {
                        "max_tokens_per_chunk": 512,
                        "max_overlap_tokens": 51,
                    }
                },
                'display_name': f'{original_name}',
            },
        )
        logger.info("SUCCESS: File %s uploaded to store %s.", file_path, store_resource)
        return {"ok": True, "store_resource": store_resource, "uploaded": True}
    except Exception as e:
        logger.error("ERROR: Could not upload file to store. Details: %s", e)
        raise


def list_file_search_stores_for_user(user_id: str) -> list:
    """
    Return list of dicts: [{"resource_name": s.name, "display_name": s.display_name}, ...]
    Only returns stores whose display_name starts with the user prefix.
    """
    try:
        prefix = _user_display_prefix(user_id)
        stores = client.file_search_stores.list()
        user_stores = []
        for s in stores:
            dn = getattr(s, "display_name", None)
            if dn and dn.startswith(prefix):
                user_stores.append({"resource_name": s.name, "display_name": dn})
        return user_stores
    except Exception as e:
        logger.error("ERROR: Could not list stores: %s", e)
        raise


def list_documents_in_store_for_user(user_id: str, display_name: str) -> list:
    """
    Returns list of docs in format expected by frontend:
    [{"resource_name": <doc_resource_name>, "display_name": <file name>, "mime_type": <type>}...]
    """
    # Check if display_name already has the prefix (from frontend)
    prefix = _user_display_prefix(user_id)
    if display_name.startswith(prefix):
        # Already has prefix, use as-is
        search_prefix = display_name
    else:
        # Add prefix
        search_prefix = _user_store_display(user_id, display_name)
    
    store_resource = _find_store_resource_by_display_prefix(search_prefix)
    if not store_resource:
        # Store doesn't exist yet or hasn't been found - return empty list instead of error
        logger.warning(f"No store found matching display prefix: {prefix}. Returning empty list.")
        return []

    try:
        documents = client.file_search_stores.documents.list(parent=store_resource)
        out = []
        for d in documents:
            # Map to frontend expected format
            out.append({
                "resource_name": getattr(d, "name", None),  # Changed from "name" to "resource_name"
                "display_name": getattr(d, "display_name", "Untitled"),
                "mime_type": getattr(d, "mime_type", "application/octet-stream")  # Added mime_type
            })
        return out
    except Exception as e:
        logger.error("ERROR: Could not list documents: %s", e)
        # Return empty list on error instead of raising
        return []


def delete_document_from_store_for_user(user_id: str, display_name: str, document_resource_name: str):
    """
    document_resource_name must be the full resource name returned in list_documents_in_store_for_user.
    """
    # Check if display_name already has the prefix (from frontend)
    prefix = _user_display_prefix(user_id)
    if display_name.startswith(prefix):
        search_prefix = display_name
    else:
        search_prefix = _user_store_display(user_id, display_name)
    
    store_resource = _find_store_resource_by_display_prefix(search_prefix)
    if not store_resource:
        raise ValueError(f"No store found matching display prefix: {prefix}")

    if not document_resource_name:
        raise ValueError("Missing document resource name to delete.")

    try:
        client.file_search_stores.documents.delete(name=document_resource_name, config={"force": True})
        logger.info("SUCCESS: Document %s deleted from store %s.", document_resource_name, store_resource)
        return {"ok": True}
    except Exception as e:
        logger.error("ERROR: Could not delete document: %s", e)
        raise


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

"""

def query_in_store_for_user(user_id: str, display_name: str, query: str) -> str:
    """
    Query documents in the store and return the response text with citations.
    Returns a formatted string with the answer and citations.
    """
    # Check if display_name already has the prefix (from frontend)
    prefix = _user_display_prefix(user_id)
    if display_name.startswith(prefix):
        search_prefix = display_name
    else:
        search_prefix = _user_store_display(user_id, display_name)
    
    store_resource = _find_store_resource_by_display_prefix(search_prefix)
    if not store_resource:
        raise ValueError(f"No store found matching display prefix: {search_prefix}")

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            
            contents=query,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[store_resource]
                        )
                    )
                ]
            )
        )


    except Exception as e:
        logger.error("ERROR: model generate_content failed: %s", e)
        raise

    # Extract the main response text
    response_text = getattr(response, "text", "") or ""
    
    # Extract citations
    citations = []
    try:
        for cand in getattr(response, "candidates", []) or []:
            gm = getattr(cand, "grounding_metadata", None)
            if not gm:
                continue
            for chunk in getattr(gm, "grounding_chunks", []) or []:
                title = getattr(chunk.retrieved_context, "title", None)
                text = getattr(chunk.retrieved_context, "text", "") or ""
                match = re.search(r"PAGE\s+(\d+)", text, flags=re.IGNORECASE)
                page = match.group(1) if match else None
                
                citation_text = f"📄 {title}"
                if page:
                    citation_text += f" (Page {page}\n)"
                
                if citation_text not in citations:
                    citations.append(citation_text)
    except Exception as e:
        logger.exception("Failed parsing grounding metadata: %s", e)

    # Format the response with citations
    if citations:
        formatted_response = f"{response_text}\n\n\n\n**Sources:**\n" + "\n".join(citations)
    else:
        formatted_response = response_text

    return formatted_response