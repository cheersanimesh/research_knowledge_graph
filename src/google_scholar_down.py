import os
import sys
import re
import requests
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse, parse_qs
import serpapi
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY")


def extract_citation_id_from_url(url: str) -> Optional[str]:
    """
    Extract citation ID from a Google Scholar citation page URL.
    
    Args:
        url: Google Scholar URL (e.g., https://scholar.google.com/scholar?cites=123...)
    
    Returns:
        Citation ID if found, None otherwise
    """
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        cites = params.get('cites', [])
        if cites:
            return cites[0]
    except Exception:
        pass
    return None


def search_google_scholar(
    query: Optional[str] = None,
    citation_id: Optional[str] = None,
    num_results: int = 20
) -> List[dict]:
    """
    Search Google Scholar using SerpAPI and extract PDF links.
    
    Args:
        query: Search query string (optional if citation_id is provided)
        citation_id: Citation ID to get papers citing a specific paper (optional)
        num_results: Maximum number of results to retrieve (default: 20)
    
    Returns:
        List of dictionaries containing paper information and PDF links
    """
    if not SERPAPI_API_KEY:
        raise ValueError("SERPAPI_API_KEY not found in environment variables. "
                        "Please set it in your .env file.")
    
    if not query and not citation_id:
        raise ValueError("Either 'query' or 'citation_id' must be provided.")
    
    # Create SerpAPI client
    client = serpapi.Client(api_key=SERPAPI_API_KEY)
    
    params = {
        "engine": "google_scholar",
        "num": 20  # Results per page (Google Scholar typically returns 10-20 per page)
    }
    
    if citation_id:
        params["cites"] = citation_id
        print(f"Fetching papers citing: {citation_id}...")
    else:
        params["q"] = query
        print(f"Searching Google Scholar for: '{query}'...")
    
    # Perform initial search
    search_results = client.search(**params)
    
    papers_with_pdfs = []
    total_results_collected = 0
    page_num = 0
    
    # Helper function to process a page of results
    def process_page(results_obj, page_number: int, current_count: int) -> int:
        """Process a page of results and return number of papers with PDFs found."""
        # Convert results to dictionary if needed
        if hasattr(results_obj, 'as_dict'):
            results = results_obj.as_dict()
        elif hasattr(results_obj, '__getitem__'):
            results = results_obj
        else:
            results = dict(results_obj)
        
        organic_results = results.get("organic_results", [])
        
        if not organic_results:
            print(f"No more results found on page {page_number}.")
            return 0
        
        print(f"Processing page {page_number}: Found {len(organic_results)} results...")
        papers_found = 0
        
        for result in organic_results:
            # Check if we've reached the target
            if current_count + papers_found >= num_results:
                break
                
            title = result.get("title", "Untitled")
            link = result.get("link", "")
            resources = result.get("resources", [])
            
            # Extract PDF links from resources
            pdf_links = []
            for resource in resources:
                if resource.get("file_format") == "PDF":
                    pdf_links.append(resource.get("link"))
            
            # Also check if the main link is a PDF
            if link and link.lower().endswith('.pdf'):
                if link not in pdf_links:
                    pdf_links.insert(0, link)
            
            if pdf_links:
                papers_with_pdfs.append({
                    "title": title,
                    "link": link,
                    "pdf_links": pdf_links
                })
                papers_found += 1
        
        return papers_found
    
    # Calculate max pages needed (assuming ~20 results per page, but not all have PDFs)
    # Estimate: if we want 100 papers with PDFs, we might need to check 200-300 total results
    # Google Scholar typically returns 10-20 results per page
    max_pages_needed = max(10, (num_results * 2) // 10 + 5)  # More generous estimate
    
    # Process the first page (initial search results)
    page_num += 1
    papers_found = process_page(search_results, page_num, total_results_collected)
    total_results_collected += papers_found
    print(f"Page {page_num}: Found {papers_found} papers with PDFs (Total so far: {total_results_collected}/{num_results})")
    
    if total_results_collected >= num_results:
        print(f"Reached target of {num_results} papers with PDFs after page {page_num}.")
    else:
        # Continue with pagination
        # Use yield_pages if available, otherwise use next_page in a loop
        if hasattr(search_results, 'yield_pages'):
            print(f"Using yield_pages() to fetch additional pages (up to {max_pages_needed} total pages)...")
            try:
                for page in search_results.yield_pages(max_pages=max_pages_needed):
                    if total_results_collected >= num_results:
                        break
                    
                    page_num += 1
                    papers_found = process_page(page, page_num, total_results_collected)
                    total_results_collected += papers_found
                    print(f"Page {page_num}: Found {papers_found} papers with PDFs (Total so far: {total_results_collected}/{num_results})")
                    
                    if total_results_collected >= num_results:
                        print(f"Reached target of {num_results} papers with PDFs after page {page_num}.")
                        break
            except Exception as e:
                print(f"Error during pagination: {e}")
        else:
            # Fallback: use next_page() in a loop
            print("Using next_page() for pagination...")
            current_results = search_results
            
            while total_results_collected < num_results and page_num < max_pages_needed:
                # Try to get next page
                if hasattr(current_results, 'next_page'):
                    try:
                        next_page = current_results.next_page()
                        if next_page and next_page != current_results:
                            current_results = next_page
                            page_num += 1
                            papers_found = process_page(current_results, page_num, total_results_collected)
                            total_results_collected += papers_found
                            print(f"Page {page_num}: Found {papers_found} papers with PDFs (Total so far: {total_results_collected}/{num_results})")
                            
                            if total_results_collected >= num_results:
                                print(f"Reached target of {num_results} papers with PDFs after page {page_num}.")
                                break
                        else:
                            print(f"No more pages available. Total pages processed: {page_num}")
                            break
                    except Exception as e:
                        print(f"Could not fetch next page: {e}. Stopping at page {page_num}.")
                        break
                else:
                    break
    
    print(f"Extracted PDF links from {len(papers_with_pdfs)} papers across {page_num} page(s).")
    
    # Print summary of found PDFs
    for paper in papers_with_pdfs:
        print(f"  ✓ Found PDF(s) for: {paper['title']}")
    
    return papers_with_pdfs


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to remove invalid characters.
    
    Args:
        filename: Original filename
    
    Returns:
        Sanitized filename safe for filesystem
    """
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove leading/trailing spaces and dots
    filename = filename.strip(' .')
    # Limit length
    if len(filename) > 200:
        filename = filename[:200]
    return filename


def download_pdf(url: str, destination: Path, filename: Optional[str] = None) -> bool:
    """
    Download a PDF from a URL to the destination directory.
    
    Args:
        url: URL of the PDF to download
        destination: Destination directory path
        filename: Optional custom filename (if not provided, extracted from URL)
    
    Returns:
        True if download successful, False otherwise
    """
    try:
        # Create destination directory if it doesn't exist
        destination.mkdir(parents=True, exist_ok=True)
        
        # Get filename from URL if not provided
        if not filename:
            filename = url.split('/')[-1]
            # Remove query parameters
            filename = filename.split('?')[0]
            if not filename.endswith('.pdf'):
                filename = f"{filename}.pdf"
        
        # Sanitize filename
        filename = sanitize_filename(filename)
        filepath = destination / filename
        
        # Skip if file already exists
        if filepath.exists():
            print(f"    ⚠ Skipping {filename} (already exists)")
            return True
        
        # Download the PDF
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30, stream=True)
        response.raise_for_status()
        
        # Check if response is actually a PDF
        content_type = response.headers.get('Content-Type', '').lower()
        if 'pdf' not in content_type and not url.lower().endswith('.pdf'):
            print(f"    ⚠ Warning: {url} may not be a PDF (Content-Type: {content_type})")
        
        # Save the file
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"    ✓ Downloaded: {filename}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"    ✗ Failed to download {url}: {str(e)}")
        return False
    except Exception as e:
        print(f"    ✗ Error downloading {url}: {str(e)}")
        return False


def download_pdfs_from_scholar(
    query: Optional[str] = None,
    destination: str = "./pdfs",
    citation_id: Optional[str] = None,
    citation_url: Optional[str] = None,
    num_results: int = 20,
    max_pdfs_per_paper: int = 1
) -> None:
    """
    Main function to search Google Scholar and download PDFs.
    
    Args:
        query: Search query string (optional if citation_id or citation_url is provided)
        destination: Destination directory path for downloaded PDFs
        citation_id: Citation ID to get papers citing a specific paper (optional)
        citation_url: Google Scholar citation page URL (optional, will extract citation_id)
        num_results: Maximum number of search results to process
        max_pdfs_per_paper: Maximum number of PDFs to download per paper (default: 1)
    """
    try:
        # Extract citation ID from URL if provided
        if citation_url:
            extracted_id = extract_citation_id_from_url(citation_url)
            if extracted_id:
                citation_id = extracted_id
                print(f"Extracted citation ID: {citation_id} from URL")
            else:
                raise ValueError(f"Could not extract citation ID from URL: {citation_url}")
        
        # Search Google Scholar
        papers_with_pdfs = search_google_scholar(
            query=query,
            citation_id=citation_id,
            num_results=num_results
        )
        
        if not papers_with_pdfs:
            print("No PDFs found in search results.")
            return
        
        print(f"\nFound {len(papers_with_pdfs)} papers with PDF links.")
        print(f"Downloading PDFs to: {destination}\n")
        
        # Convert destination to Path object
        dest_path = Path(destination)
        
        # Download PDFs
        total_downloaded = 0
        total_failed = 0
        
        for i, paper in enumerate(papers_with_pdfs, 1):
            title = paper["title"]
            pdf_links = paper["pdf_links"][:max_pdfs_per_paper]  # Limit PDFs per paper
            
            print(f"[{i}/{len(papers_with_pdfs)}] Processing: {title}")
            
            for pdf_link in pdf_links:
                # Create filename from paper title
                filename = f"{sanitize_filename(title)}.pdf"
                # If multiple PDFs, add index
                if len(pdf_links) > 1:
                    idx = pdf_links.index(pdf_link) + 1
                    filename = f"{sanitize_filename(title)}_{idx}.pdf"
                
                if download_pdf(pdf_link, dest_path, filename):
                    total_downloaded += 1
                else:
                    total_failed += 1
            print()
        
        print("=" * 60)
        print(f"Download complete!")
        print(f"  Successfully downloaded: {total_downloaded} PDF(s)")
        print(f"  Failed downloads: {total_failed}")
        print(f"  Destination: {dest_path.absolute()}")
        print("=" * 60)
        
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """
    Command-line interface for the script.
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Download PDFs from Google Scholar search results using SerpAPI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search by query
  python google_scholar_down.py --query "machine learning" --destination ./pdfs
  
  # Download from citation page URL
  python google_scholar_down.py --citation-url "https://scholar.google.com/scholar?cites=123..." --destination ./pdfs
  
  # Download using citation ID directly
  python google_scholar_down.py --citation-id "12323590702419478298" --destination ./pdfs
        """
    )
    parser.add_argument(
        "--query",
        type=str,
        help="Search query for Google Scholar"
    )
    parser.add_argument(
        "--citation-url",
        type=str,
        help="Google Scholar citation page URL (e.g., https://scholar.google.com/scholar?cites=123...)"
    )
    parser.add_argument(
        "--citation-id",
        type=str,
        help="Citation ID to get papers citing a specific paper"
    )
    parser.add_argument(
        "--destination",
        type=str,
        default="./pdfs",
        help="Destination directory path for downloaded PDFs (default: ./pdfs)"
    )
    parser.add_argument(
        "--num-results",
        type=int,
        default=20,
        help="Maximum number of search results to process (default: 20)"
    )
    parser.add_argument(
        "--max-pdfs-per-paper",
        type=int,
        default=1,
        help="Maximum number of PDFs to download per paper (default: 1)"
    )
    
    args = parser.parse_args()
    
    # Validate that at least one search method is provided
    if not args.query and not args.citation_url and not args.citation_id:
        parser.error("At least one of --query, --citation-url, or --citation-id must be provided.")
    
    download_pdfs_from_scholar(
        query=args.query,
        destination=args.destination,
        citation_id=args.citation_id,
        citation_url=args.citation_url,
        num_results=args.num_results,
        max_pdfs_per_paper=args.max_pdfs_per_paper
    )


if __name__ == "__main__":
    main()
