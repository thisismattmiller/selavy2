import difflib
import re
from typing import List, Dict, Any
from difflib import SequenceMatcher


def build_doc_diffs(text_original: str, text_processed: str) -> List[Dict[str, Any]]:
    """
    Find differences between original text and processed text with markup.
    
    Args:
        text_original: Original text without markup
        text_processed: Text with markup in format {WORD|Number|Type of Word}
    
    Returns:
        List of dictionaries containing differences with context
    """
    # Remove <BLOCKBREAK/> tags from text_processed
    text_processed = text_processed.replace('<BLOCKBREAK/>', '')
    
    # Normalize the markup in text_processed
    # Pattern matches {WORD|Number|Type} and replaces with just WORD
    normalized_text = re.sub(r'\{([^|]+)\|[^|]+\|[^}]+\}', r'\1', text_processed)
    
    # Normalize whitespace in both texts
    # Replace multiple spaces with single space and strip trailing/leading spaces per line
    text_original_normalized = '\n'.join(
        ' '.join(line.split()) for line in text_original.splitlines()
    )
    normalized_text = '\n'.join(
        ' '.join(line.split()) for line in normalized_text.splitlines()
    )
    
    # Use difflib to find differences
    differ = difflib.unified_diff(
        text_original_normalized.splitlines(keepends=True),
        normalized_text.splitlines(keepends=True),
        lineterm='',
        n=3  # Context lines
    )
    
    # Parse the diff output into structured format
    differences = []
    diff_lines = list(differ)
    
    if not diff_lines:
        return differences
    
    # Skip the header lines (---, +++)
    i = 0
    while i < len(diff_lines) and (diff_lines[i].startswith('---') or diff_lines[i].startswith('+++')):
        i += 1
    
    current_diff = None
    
    while i < len(diff_lines):
        line = diff_lines[i]
        
        if line.startswith('@@'):
            # New diff section
            if current_diff:
                differences.append(current_diff)
            
            # Parse the line numbers from @@ -a,b +c,d @@
            match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if match:
                current_diff = {
                    'original_line_start': int(match.group(1)),
                    'original_line_count': int(match.group(2) or 1),
                    'processed_line_start': int(match.group(3)),
                    'processed_line_count': int(match.group(4) or 1),
                    'context_before': [],
                    'removed_lines': [],
                    'added_lines': [],
                    'context_after': []
                }
        elif line.startswith('-') and not line.startswith('---'):
            # Line removed from original
            if current_diff:
                current_diff['removed_lines'].append(line[1:].rstrip('\n'))
        elif line.startswith('+') and not line.startswith('+++'):
            # Line added in processed
            if current_diff:
                current_diff['added_lines'].append(line[1:].rstrip('\n'))
        elif line.startswith(' '):
            # Context line
            if current_diff:
                # Determine if this is before or after the changes
                if not current_diff['removed_lines'] and not current_diff['added_lines']:
                    current_diff['context_before'].append(line[1:].rstrip('\n'))
                else:
                    current_diff['context_after'].append(line[1:].rstrip('\n'))
        
        i += 1
    
    # Add the last diff if exists
    if current_diff:
        differences.append(current_diff)
    
    # Create a more readable format
    formatted_differences = []
    for diff in differences:
        original_text = ' '.join(diff['removed_lines'])
        processed_text = ' '.join(diff['added_lines'])
        
        # Skip if both original and processed are empty (no actual changes)
        if not original_text and not processed_text:
            continue
        
        # Skip if the only difference is whitespace
        if original_text.strip() == processed_text.strip():
            continue
        
        formatted_diff = {
            'type': 'modification' if diff['removed_lines'] and diff['added_lines'] else 
                    'deletion' if diff['removed_lines'] else 'addition',
            'location': {
                'original_line': diff['original_line_start'],
                'processed_line': diff['processed_line_start']
            },
            'context': {
                'before': ' '.join(diff['context_before'][-2:]) if diff['context_before'] else '',
                'after': ' '.join(diff['context_after'][:2]) if diff['context_after'] else ''
            },
            'changes': {
                'original': original_text,
                'processed': processed_text
            }
        }
        
        # Generate marked up versions with <strong> tags around differences
        if formatted_diff['type'] == 'modification':
            # Find word-level differences and wrap them in <strong> tags
            original_markedup = highlight_differences(original_text, processed_text, is_original=True)
            processed_markedup = highlight_differences(original_text, processed_text, is_original=False)
            
            formatted_diff['changes_markedup'] = {
                'original': original_markedup,
                'processed': processed_markedup
            }
            formatted_diff['description'] = f"Text changed from '{original_text[:50]}...' to '{processed_text[:50]}...'"
        elif formatted_diff['type'] == 'deletion':
            formatted_diff['changes_markedup'] = {
                'original': f'<strong>{original_text}</strong>',
                'processed': ''
            }
            formatted_diff['description'] = f"Text removed: '{original_text[:50]}...'"
        else:
            formatted_diff['changes_markedup'] = {
                'original': '',
                'processed': f'<strong>{processed_text}</strong>'
            }
            formatted_diff['description'] = f"Text added: '{processed_text[:50]}...'"
        
        formatted_differences.append(formatted_diff)
    
    return formatted_differences


def highlight_differences(text1: str, text2: str, is_original: bool) -> str:
    """
    Highlight differences between two texts at word level.
    
    Args:
        text1: Original text
        text2: Processed text
        is_original: True if highlighting for original text, False for processed
    
    Returns:
        Text with <strong> tags around different words
    """
    words1 = text1.split()
    words2 = text2.split()
    
    matcher = SequenceMatcher(None, words1, words2)
    result = []
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            # Words are the same
            if is_original:
                result.extend(words1[i1:i2])
            else:
                result.extend(words2[j1:j2])
        elif tag == 'delete':
            # Words deleted from original
            if is_original:
                result.extend([f'<strong>{word}</strong>' for word in words1[i1:i2]])
        elif tag == 'insert':
            # Words inserted in processed
            if not is_original:
                result.extend([f'<strong>{word}</strong>' for word in words2[j1:j2]])
        elif tag == 'replace':
            # Words replaced
            if is_original:
                result.extend([f'<strong>{word}</strong>' for word in words1[i1:i2]])
            else:
                result.extend([f'<strong>{word}</strong>' for word in words2[j1:j2]])
    
    return ' '.join(result)