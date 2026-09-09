import sys
import subprocess

print(f"Python version: {sys.version}")
print(f"Python path: {sys.path}")

try:
    import codecartographer
    print(f"✅ codecartographer trouvé : {codecartographer.__file__}")
except ImportError as e:
    print(f"❌ Erreur d'import : {e}")

# Vérifier le point d'entrée
try:
    result = subprocess.run(['ccart', '--help'], capture_output=True, text=True)
    print(f"Résultat ccart: {result.stdout[:200]}...")
except Exception as e:
    print(f"❌ Erreur ccart : {e}")
