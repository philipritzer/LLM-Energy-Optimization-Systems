import base64
import os
import warnings
from io import BytesIO

import streamlit as st
from langchain_core.messages import HumanMessage
from langchain_experimental.tools import PythonREPLTool
from langchain_openai import ChatOpenAI

import auth_keys
from shared_utils import (get_weather_forecast, create_agent, format_response, get_summed_historic_data, get_live_data)

warnings.filterwarnings("ignore")

os.environ["OPENAI_API_KEY"] = auth_keys.openai_api_key
os.environ["OPENWEATHERMAP_API_KEY"] = auth_keys.openweather_api_key

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = auth_keys.langchain_api_key
os.environ["LANGCHAIN_PROJECT"] = "single_agent"

python_repl_tool = PythonREPLTool()

llm = ChatOpenAI(model='gpt-4o', temperature=0)

agent_all = create_agent(llm=llm,
                         tools=[get_weather_forecast, python_repl_tool, get_summed_historic_data, get_live_data],
                         system_prompt="You are the Weather Retriever, Energy Optimizer, and Python Code Generator. "
                                       "Your task is to provide the current weather and weather forecast for a "
                                       "predefined location, analyze solar and weather data to provide insights on "
                                       "energy usage and optimization, and generate safe Python code to analyze data "
                                       "and create charts using matplotlib. If your task ist to plot solar data you "
                                       "can request time series data with python from the endpoint "
                                       "<insert url here> "
                                       "which returns CSV data covering the last three days with keys for "
                                       "production (kWh), grid (kWh), consumption (kWh), timestamp ("
                                       "YYYY-MM-DDTHH:MM:SS format), and battery_status (%). When analyzing energy "
                                       "usage, prioritize power from solar panels and recommend energy-intensive "
                                       "tasks during sunny periods to utilize free solar energy. Consider the "
                                       "following hierarchy of factors: 1) Solar Production, prioritizing "
                                       "recommendations for periods with highest expected solar energy production, "
                                       "2) Weather Conditions, considering cloud cover and precipitation affecting "
                                       "solar production, and 3) Temperature, suggesting energy-intensive tasks "
                                       "during favorable temperatures if solar production is insufficient. Provide "
                                       "insights on non-optimal energy usage periods, suggest optimal times for high "
                                       "energy consumption based on solar production and weather forecasts, "
                                       "and offer general energy-saving recommendations. When analyzing data or "
                                       "visualizations, provide tips on interpretation and further analysis. Treat "
                                       "all information as your own, without referencing separate roles or "
                                       "interactions. Always answer in the language of the prompt.")

config = {"recursion_limit": 7}


def generate_response(input_text):
    output = agent_all.invoke({
        "messages": [HumanMessage(
            input_text)]
    }, config=config)
    return output.get("output")


def main():
    st.title("Single-Agenten System")

    user_input = st.text_input("Enter your request:", "")

    if st.button("Generate Response"):
        if user_input:
            with st.spinner("Generating response..."):
                response = generate_response(user_input)
                formatted_text, image_data = format_response(response)

                st.markdown(formatted_text, unsafe_allow_html=True)

                if image_data:
                    image = BytesIO(base64.b64decode(image_data))
                    st.image(image, caption="Generated Plot", use_column_width=True)
        else:
            st.warning("Please enter a request.")


if __name__ == "__main__":
    main()
