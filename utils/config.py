from dotenv import load_dotenv
load_dotenv()

class Config:
    token = os.getenv("TOKEN")
