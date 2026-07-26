import smtplib
import ssl
import os
from email.message import EmailMessage
from config import config

class EmailSender:
    def __init__(self):
        self.sender_email = config.get("SENDER_EMAIL")
        self.password = config.get("GMAIL_APP_PASSWORD")
        if not self.sender_email or not self.password:
            raise ValueError("SENDER_EMAIL or GMAIL_APP_PASSWORD is missing in configuration.")
            
    def send_outreach_email(self, recipient_email, company_name, cover_letter_path, cv_path, role_title="DevOps & Cloud Engineer"):
        """
        Sends an outreach email with the CV and cover letter attached.
        """
        if not recipient_email:
            print("[EmailSender] Error: Recipient email is empty.")
            return False
            
        msg = EmailMessage()
        msg["From"] = self.sender_email
        msg["To"] = recipient_email
        msg["Subject"] = f"DevOps & Cloud Engineering Application - Abraham Gyamfi"

        # Email body (highly professional and brief)
        body = (
            f"Dear Recruiting Team at {company_name},\n\n"
            f"I hope this email finds you well.\n\n"
            f"My name is Abraham Gyamfi. I am a Computer Science graduate from KNUST, "
            f"an AWS Certified Solutions Architect – Associate, and an active DevOps Engineer at AmaliTech.\n\n"
            f"I am writing to express my strong interest in DevOps and Cloud Engineering opportunities at {company_name}. "
            f"To share details on how my background aligns with your work, I have attached my CV and a tailored cover letter.\n\n"
            f"Some highlights of my work include:\n"
            f"- Architecting highly available AWS infrastructure (EC2, RDS, DynamoDB, S3, EKS, Lambda, ECS) using modular Terraform and CloudFormation.\n"
            f"- Deploying, managing, and scaling containerized workloads on Kubernetes (Amazon EKS) for resilient, highly available applications.\n"
            f"- Designing and maintaining automated CI/CD pipelines with Jenkins, integrating security testing into deployment workflows.\n"
            f"- Implementing monitoring and logging architectures using AWS CloudWatch, Prometheus, and Grafana to improve system visibility and reduce MTTR.\n"
            f"- Automating routine infrastructure maintenance with Bash and Python to reduce manual overhead.\n\n"
            f"I would welcome the opportunity to speak briefly with a member of your team or engineering leads about how "
            f"my automation skills and operational experience can add value to {company_name}.\n\n"
            f"Thank you for your time and consideration.\n\n"
            f"Best regards,\n\n"
            f"Abraham Gyamfi\n"
            f"Kumasi, Ghana\n"
            f"Phone: +233 55 784 9795\n"
            f"LinkedIn: https://www.linkedin.com/in/opoku-gyamfi-abraham-959980392\n"
            f"GitHub: https://github.com/AbrahamGyamfi\n"
        )
        msg.set_content(body)
        
        # Attach Cover Letter
        if os.path.exists(cover_letter_path):
            with open(cover_letter_path, "rb") as f:
                file_data = f.read()
                file_name = os.path.basename(cover_letter_path)
            msg.add_attachment(file_data, maintype="application", subtype="pdf", filename=file_name)
        else:
            print(f"[EmailSender] Error: Cover letter path {cover_letter_path} does not exist.")
            return False
            
        # Attach CV
        if os.path.exists(cv_path):
            with open(cv_path, "rb") as f:
                file_data = f.read()
                file_name = os.path.basename(cv_path)
            msg.add_attachment(file_data, maintype="application", subtype="pdf", filename=file_name)
        else:
            print(f"[EmailSender] Error: CV path {cv_path} does not exist.")
            return False
            
        # Send email
        context = ssl.create_default_context()
        try:
            print(f"[EmailSender] Connecting to SMTP server to email {recipient_email}...")
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
                smtp.login(self.sender_email, self.password)
                smtp.sendmail(self.sender_email, recipient_email, msg.as_string())
            print(f"[EmailSender] Successfully sent email to {recipient_email}")
            return True
        except Exception as e:
            print(f"[EmailSender] SMTP Error sending to {recipient_email}: {e}")
            return False
