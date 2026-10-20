"""Configure a Groq key via hidden input without printing the credential."""
import getpass
import re
import subprocess
from .config import ROOT


def configure():
    path=ROOT/'.env'
    result=subprocess.run(['git','check-ignore','--quiet','.env'],cwd=ROOT)
    if result.returncode != 0:raise SystemExit('Refusing to save: .env is not ignored by Git.')
    key=getpass.getpass('Groq API key (hidden): ').strip()
    if not re.fullmatch(r'gsk_[A-Za-z0-9_-]{20,200}',key):raise SystemExit('Invalid key format. Nothing saved.')
    updates={'GROQ_API_KEY':key,'GROQ_MODEL':'openai/gpt-oss-20b','RESEARCH_PROVIDER':'groq'}
    existing=path.read_text(encoding='utf-8-sig').splitlines() if path.exists() else []
    lines=[line for line in existing if line.partition('=')[0].strip() not in updates]
    lines.extend(name+'='+value for name,value in updates.items())
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Groq configuration saved locally. Credential was not displayed. Restart the app to apply it.')


if __name__=='__main__':configure()
