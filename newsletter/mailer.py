"""
이메일 발송 모듈 - MJML 템플릿 → 이메일 전용 HTML 변환 후 발송
"""
import smtplib, os, base64, uuid, mimetypes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import encoders
from email.header import Header
from email.utils import formataddr
from jinja2 import Environment, FileSystemLoader
import mjml

TEMPLATE_DIR = os.path.dirname(os.path.abspath(__file__))

def apply_theme_palette(html: str, primary: str, secondary: str, accent: str, bg: str, footer: str) -> str:
    replacements = {
        "#b71c1c": secondary,
        "#c62828": primary,
        "#ef5350": accent,
        "#fff5f5": bg,
        "#fffafa": bg,
        "#f8d7da": bg,
        "#f5c6cb": bg,
        "#0055a4": primary,
        "#0077cc": secondary,
        "#0099ff": accent,
        "#f4f6f9": bg,
        "#8e0000": footer,
    }
    for old, new in replacements.items():
        html = html.replace(old, new).replace(old.upper(), new)
    return html

def render_email_html(data: dict, image_cid: str = "", logo_cid: str = "", crf_cid: str = "") -> str:
    """MJML 템플릿 → Jinja2 렌더링 → MJML 컴파일 → 이메일용 HTML"""
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

    # 1. MJML 템플릿에 Jinja2 변수 주입
    mjml_tmpl = env.get_template("template.mjml")
    crf_guideline_link = f"cid:{crf_cid}" if crf_cid else data.get("crf_guideline_link", "")
    render_data = {k: v for k, v in data.items() if k not in ("crf_guideline_link", "schedule_image_cid", "logo_cid")}
    rendered_mjml = mjml_tmpl.render(
        **render_data,
        schedule_image_cid=image_cid,
        logo_cid=logo_cid,
        crf_guideline_link=crf_guideline_link,
    )

    # 2. MJML → HTML 컴파일
    result = mjml.mjml_to_html(rendered_mjml)
    if result.errors:
        raise RuntimeError(f"MJML 컴파일 오류: {result.errors}")
    return result.html

def send_newsletter(
    to_email: str,
    to_name: str,
    subject: str,
    html_body: str,          # 웹 미리보기용 (사용 안 함, 호환성 유지)
    smtp_host: str = None,
    smtp_port: int = None,
    smtp_user: str = None,
    smtp_pass: str = None,
    template_data: dict = None,
    image_path: str = "",
    logo_path: str = "",
    attachment_path: str = "",
) -> dict:
    host = smtp_host or os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
    user = smtp_user or os.getenv("SMTP_USER", "")
    pwd  = smtp_pass or os.getenv("SMTP_PASS", "")

    # 포트 25 (사내 릴레이)는 인증 없이도 허용
    if not user and port != 25:
        return {"ok": False, "error": "SMTP 계정 정보 없음"}

    try:
        msg = MIMEMultipart("related")
        msg["Subject"] = subject
        msg["From"]    = formataddr((str(Header("광동제약", "utf-8")), user))
        msg["To"]      = to_email

        # 이미지 CID 처리
        image_cid = ""
        logo_cid = ""
        crf_cid = ""
        img_mime = None
        logo_mime = None
        att_mime = None
        if image_path and os.path.exists(image_path):
            image_cid = f"scheduleimg_{uuid.uuid4().hex[:8]}"
            with open(image_path, "rb") as f:
                img_data = f.read()
            ext = os.path.splitext(image_path)[-1].lower().replace(".", "")
            ext = "jpeg" if ext == "jpg" else ext
            img_mime = MIMEImage(img_data, _subtype=ext)
            img_mime.add_header("Content-ID", f"<{image_cid}>")
            img_mime.add_header("Content-Disposition", "inline")

        # CRF 첨부파일 처리
        if attachment_path and os.path.exists(attachment_path):
            crf_cid = f"crfguideline_{uuid.uuid4().hex[:8]}"
            with open(attachment_path, "rb") as f:
                att_data = f.read()
            att_ext = os.path.splitext(attachment_path)[-1].lower()
            att_name = f"CRF_Completion_Guideline{att_ext}"
            mime_type, _ = mimetypes.guess_type(attachment_path)
            main_type, sub_type = (mime_type or "application/octet-stream").split("/", 1)
            att_mime = MIMEBase(main_type, sub_type)
            att_mime.set_payload(att_data)
            encoders.encode_base64(att_mime)
            att_mime.add_header("Content-ID", f"<{crf_cid}>")
            att_mime.add_header("Content-Disposition", "attachment", filename=att_name)

        # 로고 CID 처리
        if logo_path and os.path.exists(logo_path):
            logo_cid = f"logoimg_{uuid.uuid4().hex[:8]}"
            with open(logo_path, "rb") as f:
                logo_data = f.read()
            logo_mime = MIMEImage(logo_data, _subtype="png")
            logo_mime.add_header("Content-ID", f"<{logo_cid}>")
            logo_mime.add_header("Content-Disposition", "inline")

        # 이메일 전용 HTML 렌더링
        if template_data:
            email_html = render_email_html(template_data, image_cid, logo_cid, crf_cid)
            theme = template_data.get("theme", {}) if isinstance(template_data, dict) else {}
            email_html = apply_theme_palette(
                email_html,
                theme.get("primary", "#c62828"),
                theme.get("secondary", "#b71c1c"),
                theme.get("accent", "#ef5350"),
                theme.get("bg", "#fff5f5"),
                theme.get("footer", "#8e0000"),
            )
        else:
            email_html = html_body  # 폴백

        alt_part = MIMEMultipart("alternative")
        alt_part.attach(MIMEText(email_html, "html", "utf-8"))
        msg.attach(alt_part)

        if img_mime:
            msg.attach(img_mime)
        if logo_mime:
            msg.attach(logo_mime)
        if att_mime:
            msg.attach(att_mime)

        with smtplib.SMTP(host, port) as server:
            server.ehlo()
            # 포트 587: STARTTLS + 인증 / 포트 25: 인증 없이 직접 릴레이
            if port == 587:
                server.starttls()
                server.login(user, pwd)
            elif user and pwd:
                server.login(user, pwd)
            server.sendmail(user or "noreply", [to_email], msg.as_string())

        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
