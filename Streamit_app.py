import pdfkit

def generate_pdf(quiz_data, level, topic):
    """Generates a styled A4 PDF document using pdfkit."""
    items_html = ""
    for i, item in enumerate(quiz_data):
        q_text = item['q']
        a_text = item['a']
        
        q_rtl_class = "rtl" if is_arabic(q_text) else ""
        a_rtl_class = "rtl-box" if is_arabic(a_text) else ""
        
        items_html += f"""
        <div class="card">
            <div class="q-title">Question {i+1}</div>
            <div class="q-text {q_rtl_class}">{q_text}</div>
            <div class="ans-box {a_rtl_class}">
                <strong>Mark Scheme / Guidance:</strong><br>
                {a_text}
            </div>
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
      @page {{
        size: A4;
        margin: 15mm;
      }}
      body {{
        font-family: Arial, sans-serif;
        color: #1e293b;
        margin: 0;
        padding: 0;
      }}
      .header-table {{
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 20px;
        border-bottom: 2px solid #004b95;
        padding-bottom: 10px;
      }}
      .header-title {{
        font-size: 20pt;
        font-weight: bold;
        color: #004b95;
      }}
      .header-meta {{
        font-size: 10pt;
        color: #64748b;
        margin-top: 4px;
      }}
      .card {{
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 12px 16px;
        margin-bottom: 14px;
        page-break-inside: avoid;
      }}
      .q-title {{
        font-size: 11pt;
        font-weight: bold;
        color: #004b95;
        margin-bottom: 4px;
      }}
      .q-text {{
        font-size: 11pt;
        font-weight: bold;
        color: #0f172a;
        margin-bottom: 8px;
      }}
      .q-text.rtl {{
        direction: rtl;
        text-align: right;
        font-size: 13pt;
      }}
      .ans-box {{
        background-color: #eff6ff;
        border-left: 4px solid #004b95;
        padding: 8px 12px;
        border-radius: 4px;
        font-size: 10pt;
        color: #1e293b;
        margin-top: 6px;
      }}
      .ans-box.rtl-box {{
        direction: rtl;
        text-align: right;
        border-left: none;
        border-right: 4px solid #004b95;
        font-size: 11pt;
      }}
    </style>
    </head>
    <body>
      <table class="header-table">
        <tr>
          <td>
            <div class="header-title">Retrieval Practice Sheet</div>
            <div class="header-meta">Exam Level: {level} | Topic: {topic}</div>
          </td>
        </tr>
      </table>
      {items_html}
    </body>
    </html>
    """
    
    options = {
        'page-size': 'A4',
        'encoding': 'UTF-8',
        'enable-local-file-access': None
    }
    
    # Render PDF bytes directly from string
    pdf_bytes = pdfkit.from_string(html_content, False, options=options)
    return pdf_bytes
