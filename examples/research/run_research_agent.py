#!/usr/bin/env python3
"""
Simple runner script for the research agent.
This script demonstrates how to use the research agent to conduct research on a topic.
"""

import os
import sys
from pathlib import Path

# Add the research directory to the path so we can import the research_agent
sys.path.insert(0, str(Path(__file__).parent))

from research_agent import agent


def main():
    """Run the research agent with a sample query."""
    
    # Check if required environment variables are set
    if not os.getenv("TAVILY_API_KEY"):
        print("❌ Error: TAVILY_API_KEY environment variable is not set.")
        print("Please get a free API key from https://tavily.com and set it:")
        print("export TAVILY_API_KEY='your_api_key_here'")
        return 1
    
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ Error: ANTHROPIC_API_KEY environment variable is not set.")
        print("Please get an API key from https://console.anthropic.com and set it:")
        print("export ANTHROPIC_API_KEY='your_api_key_here'")
        return 1
    
    # Sample research question - you can modify this
    research_question = input("Enter your research question (or press Enter for default): ").strip()
    
    if not research_question:
        research_question = "What are the latest developments in artificial intelligence in 2024?"
    
    print(f"\n🔍 Starting research on: {research_question}")
    print("=" * 60)
    
    try:
        # Run the research agent
        result = agent.invoke({
            "messages": [{"role": "user", "content": research_question}]
        })
        
        print("\n✅ Research completed!")
        print("=" * 60)
        
        # Print the final response
        if result and "messages" in result:
            final_message = result["messages"][-1]
            print(f"\n{final_message['content']}")
        
        # Check if files were created
        report_file = Path("final_report.md")
        question_file = Path("question.txt")
        
        if report_file.exists():
            print(f"\n📄 Report saved to: {report_file.absolute()}")
        
        if question_file.exists():
            print(f"📝 Question saved to: {question_file.absolute()}")
            
    except Exception as e:
        print(f"\n❌ Error during research: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
