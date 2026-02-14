import urllib.request
import ssl

try:
    # Bypass SSL verification if needed (common in some corporate/local envs, though less secure)
    context = ssl._create_unverified_context()
    
    req = urllib.request.Request(
        'https://catalog.aucegypt.edu/preview_program.php?catoid=44&poid=8170', 
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    with urllib.request.urlopen(req, context=context) as response:
        print(response.read().decode('utf-8')[:500])
except Exception as e:
    print(f"Error: {e}")
