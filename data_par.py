import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
from fpdf import FPDF

# -- Environment & Gemini config ------------------------------------------------
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-3-flash-preview")

# -- Helper functions -----------------------------------------------------------

def desc_columns(df: pd.DataFrame) -> str:
    description = [f"`{col}`: {str(df[col].dtype)}" for col in df.columns]
    return "DataFrame column descriptions:\n" + "\n".join(description)


def load_file(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    elif name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)
    else:
        raise ValueError(f"Unsupported file format: {uploaded_file.name}")


def generate_pandas_code(df: pd.DataFrame, question: str) -> str:
    prompt = (
        "You are working with a pandas dataframe in Python.\n"
        "The name of the dataframe is `df`.\n"
        f"{desc_columns(df)}\n\n"
        "This is the result of `print(df.head())`:\n"
        f"{df.head(5).to_string()}\n\n"
        "RULES — follow strictly:\n"
        "1. Convert the query to executable Python code using Pandas.\n"
        "2. The final line of code must be a pure data expression evaluable with `eval()`.\n"
        "3. The code should represent a solution to the query.\n"
        "4. PRINT ONLY THE EXPRESSION, nothing else.\n"
        "5. Do not quote the expression.\n"
        "6. NEVER use .plot(), matplotlib, seaborn or any visualisation library. Data only.\n"
        "7. If the question asks for a chart or graph, return only the aggregated data behind it (e.g. groupby + sum/mean).\n\n"
        f"Query: {question}\n\n"
        "Expression:"
    )
    response = model.generate_content(prompt)
    code = response.text.strip()
    # Strip markdown code fences if present
    if code.startswith("```"):
        code = "\n".join(code.split("\n")[1:])
    if code.endswith("```"):
        code = "\n".join(code.split("\n")[:-1])
    return code.strip()


def execute_pandas_code(df: pd.DataFrame, code: str) -> str:
    try:
        result = eval(code, {"df": df, "pd": pd})
        return str(result)
    except Exception as exc:
        return f"Error executing code: {exc}"


def synthesize_response(question: str, pandas_code: str, pandas_output: str) -> str:
    prompt = (
        "You are an expert data analyst. Answer the question below using the pandas results provided.\n\n"
        "FORMATTING RULES — follow them strictly:\n"
        "- Structure the response with clear Markdown: use headers (##, ###), bold, bullet lists and tables where appropriate.\n"
        "- Use emojis to make the response visual and engaging:\n"
        "  🔢 for counts and totals | 💰 for monetary / financial values | 📈 for growth / increase trends\n"
        "  📉 for decline / decrease trends | 🔍 for insights and findings | ⚠️ for warnings or anomalies\n"
        "  📊 for distributions / statistics | 🏆 for top / best values | 🗓️ for dates / time periods\n"
        "  ✅ for confirmations | ❌ for negatives / missing data | 💡 for conclusions and recommendations\n"
        "- If the answer is a single number or short fact, present it prominently inside a Markdown blockquote (> ...).\n"
        "- If the answer contains multiple values, use a Markdown table or a bullet list.\n"
        "- End with a '---' divider followed by a collapsible section:\n"
        "  <details><summary>🛠️ Code used</summary>\n\n```python\n<the pandas code>\n```\n\n</details>\n\n"
        "- Do NOT start with phrases like 'The answer is' or 'Here is your answer'.\n\n"
        f"**Question:** {question}\n\n"
        f"**Pandas code executed:**\n```python\n{pandas_code}\n```\n\n"
        f"**Pandas output:** {pandas_output}\n\n"
        "**Your structured response:**"
    )
    response = model.generate_content(prompt)
    return response.text


def generate_plotly_code(df: pd.DataFrame, question: str) -> str:
    prompt = (
        "You are a data visualisation expert working with a pandas DataFrame called `df` in Python.\n"
        f"{desc_columns(df)}\n\n"
        "This is the result of `print(df.head())`:  \n"
        f"{df.head(5).to_string()}\n\n"
        "TASK: Decide if the user request below benefits from a chart.\n\n"
        "STRICT RULES — violating any rule makes the response invalid:\n"
        "  1. You MUST use ONLY plotly.express (imported as `px`). It is already available.\n"
        "  2. NEVER use matplotlib, seaborn, pandas .plot(), or any other plotting library.\n"
        "  3. NEVER import matplotlib or call plt / fig.show() / plt.show().\n"
        "  4. Store the figure in a variable named exactly `fig`.\n"
        "  5. The LAST line of code must be exactly: fig\n"
        "  6. Choose the most appropriate px chart type: px.bar, px.line, px.scatter, px.pie,\n"
        "     px.histogram, px.box, px.violin, px.area, px.imshow, px.sunburst, etc.\n"
        "  7. Always set a descriptive `title`. Use `labels` and `color` where relevant.\n"
        "  8. Output ONLY plain Python code — no markdown fences, no comments, no explanations.\n"
        "  - If NO chart is relevant (e.g. question asks only for a number or text), respond with exactly: NO_CHART\n\n"
        f"User request: {question}\n\n"
        "Python code using plotly.express only (or NO_CHART):"
    )
    response = model.generate_content(prompt)
    code = response.text.strip()
    if code.startswith("```"):
        code = "\n".join(code.split("\n")[1:])
    if code.endswith("```"):
        code = "\n".join(code.split("\n")[:-1])
    return code.strip()


def execute_plotly_code(df: pd.DataFrame, code: str):
    """Executes the Plotly code and returns a Figure, or None on failure."""
    if not code or code.upper() == "NO_CHART":
        return None
    try:
        namespace = {"df": df, "pd": pd, "px": px}
        exec(code, namespace)  # noqa: S102
        fig = namespace.get("fig")
        # Validate it's actually a Plotly figure
        if fig is not None and hasattr(fig, "to_dict"):
            return fig
        return None
    except Exception:
        return None


def process_question(df: pd.DataFrame, question: str) -> tuple:
    """Returns (response_text, plotly_figure | None)."""
    pandas_code = generate_pandas_code(df, question)
    pandas_output = execute_pandas_code(df, pandas_code)
    response_text = synthesize_response(question, pandas_code, pandas_output)
    plotly_code = generate_plotly_code(df, question)
    fig = execute_plotly_code(df, plotly_code)
    return response_text, fig


def generate_pdf(history: list) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    for question, response in history:
        pdf.set_font("Arial", "B", 14)
        safe_q = question.encode("latin-1", "replace").decode("latin-1")
        pdf.multi_cell(0, 8, txt=safe_q)
        pdf.ln(2)
        pdf.set_font("Arial", "", 12)
        safe_r = response.encode("latin-1", "replace").decode("latin-1")
        pdf.multi_cell(0, 8, txt=safe_r)
        pdf.ln(6)
    return bytes(pdf.output())


# -- Session state initialisation ----------------------------------------------
def init_state():
    defaults = {
        "df": None,
        "history": [],
        "response": "",
        "question": "",
        "pdf_bytes": None,
        "figure": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# -- Streamlit UI ---------------------------------------------------------------
st.set_page_config(
    page_title="AI-Powered Data Analysis",
    page_icon=":robot_face:",
    layout="wide",
)

init_state()

st.title("🤖🔎 AI-Powered Data Analysis")

# -- Sidebar -------------------------------------------------------------------
with st.sidebar:
    st.header("How to use")
    st.markdown(
        """
1. 📤 **Upload** a CSV or Excel file.
2. ❓ **Ask** any question about your data.
3. ➕ **Add** interesting answers to the report history.
4. 📄 **Generate** and download the PDF report.
5. 🔄 **Reset** to analyse a new file.
"""
    )
    st.divider()
    st.subheader("❓ Ask a question about your data")

    st.caption("**Example questions:**")
    st.markdown(
        """
- What is the total number of records in this dataset?
- List all distinct values in each categorical column.
- What data types are stored in each column?
- Provide a statistical summary for the numerical columns.
- Are there any missing values? If so, in which columns?
"""
    )
    st.divider()
    st.caption("Powered by **Gemini 3 Flash**")

# -- File upload ---------------------------------------------------------------
uploaded_file = st.file_uploader(
    "📤 Upload your data file",
    type=["csv", "xlsx", "xls"],
    help="Supported formats: CSV, Excel (.xlsx, .xls)",
)

if uploaded_file is not None:
    try:
        st.session_state.df = load_file(uploaded_file)
        st.success(
            f"✅ File **{uploaded_file.name}** loaded — "
            f"{st.session_state.df.shape[0]} rows × {st.session_state.df.shape[1]} columns."
        )
    except Exception as exc:
        st.error(f"❌ Error loading file: {exc}")
        st.session_state.df = None

# -- Data preview --------------------------------------------------------------
if st.session_state.df is not None:
    with st.expander("📊 Data preview", expanded=True):
        st.dataframe(st.session_state.df.head(5), width="content")

    st.divider()

    with st.form("question_form", clear_on_submit=False, border=False):
        question_input = st.text_area(
            "❓ Type your question here  *(Ctrl+Enter to submit)*",
            value=st.session_state.question,
            height=80,
            placeholder="e.g. What is the average value of column X?",
        )
        col1, col2, col3 = st.columns([1, 1, 4])
        with col1:
            submit = st.form_submit_button("🔍 Submit", type="secondary", width="stretch")
        with col2:
            clear = st.form_submit_button("🗑️ Clear", width="stretch")

    if clear:
        st.session_state.question = ""
        st.session_state.response = ""
        st.session_state.figure = None
        st.rerun()

    if submit:
        if not question_input.strip():
            st.warning("Please enter a question before submitting.")
        else:
            st.session_state.question = question_input
            st.session_state.figure = None
            with st.spinner("Analysing your data with Gemini..."):
                st.session_state.response, st.session_state.figure = process_question(
                    st.session_state.df, question_input
                )

    if st.session_state.response:
        st.markdown(st.session_state.response, unsafe_allow_html=True)

        if st.session_state.figure is not None:
            st.plotly_chart(st.session_state.figure, width="content")

        if st.button("➕ Add this answer to the PDF report"):
            if st.session_state.question and st.session_state.response:
                st.session_state.history.append(
                    (st.session_state.question, st.session_state.response)
                )
                st.success("✅ Added to report history!")

# -- PDF report ----------------------------------------------------------------
st.divider()
st.subheader("📋 Report history")

if st.session_state.history:
    st.info(f"{len(st.session_state.history)} item(s) in report history.")

    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("📥 Generate PDF", type="primary", width="content"):
            with st.spinner("Generating PDF..."):
                st.session_state.pdf_bytes = generate_pdf(st.session_state.history)
    with col2:
        if st.session_state.pdf_bytes:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            st.download_button(
                label="⬇️ Download PDF",
                data=st.session_state.pdf_bytes,
                file_name=f"report_{timestamp}.pdf",
                mime="application/pdf",
                type="secondary",
                width="content",
            )
else:
    st.caption("No items in the report history yet. Submit questions and add answers above.")

# -- Reset ---------------------------------------------------------------------
st.divider()
if st.button("🔄 Reset — Parse a new file", type="secondary"):
    for key in ["df", "history", "response", "question", "pdf_bytes", "figure"]:
        if key in ("df", "pdf_bytes", "figure"):
            st.session_state[key] = None
        elif key == "history":
            st.session_state[key] = []
        else:
            st.session_state[key] = ""
    st.rerun()
