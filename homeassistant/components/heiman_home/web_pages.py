"""Web pages for OAuth2 callback and error display."""

import logging

_LOGGER = logging.getLogger(__name__)


async def oauth_redirect_page(
    title: str,
    content: str,
    button: str,
    success: bool = True,
) -> str:
    """Generate HTML page for OAuth2 redirect.

    Args:
        title: Page title
        content: Page content/message
        button: Button text
        success: Whether the page shows success or error

    Returns:
        str: HTML content
    """
    color = "#1FA344" if success else "#DC2626"
    icon = "✓" if success else "✕"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .container {{
            background: white;
            border-radius: 16px;
            padding: 40px;
            max-width: 500px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            text-align: center;
        }}
        .icon {{
            font-size: 64px;
            color: {color};
            margin-bottom: 20px;
            display: inline-block;
            width: 100px;
            height: 100px;
            line-height: 100px;
            border-radius: 50%;
            background: {color}20;
        }}
        h1 {{
            color: #1f2937;
            margin: 0 0 16px 0;
            font-size: 24px;
            font-weight: 600;
        }}
        p {{
            color: #6b7280;
            line-height: 1.6;
            margin: 0 0 30px 0;
        }}
        .btn {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 32px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
        }}
        .btn:active {{
            transform: translateY(0);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">{icon}</div>
        <h1>{title}</h1>
        <p>{content}</p>
        <button class="btn" onclick="window.close()">{button}</button>
    </div>
</body>
</html>"""
