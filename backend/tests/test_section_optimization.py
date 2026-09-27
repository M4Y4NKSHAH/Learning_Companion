import os
import sys
import pytest

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from material_parser import MaterialParser


def test_academic_header_detection():
    sample_text = """
    Lecture 1: The Foundations of Classical Economics
    Economics is the study of how society manages its scarce resources. In most societies,
    resources are allocated not by an all-powerful dictator but through the combined choices of millions of households.
    Market economies allow buyers and sellers to interact dynamically to set prices and equilibrium.

    Lecture 2: Market Equilibrium and Price Signals
    When supply meets demand, prices coordinate the actions of self-interested buyers and sellers.
    Adam Smith described this as an invisible hand guiding market participants toward desirable social outcomes.
    Shortages and surpluses are automatically resolved when price is permitted to adjust.

    Topic 3: Government Intervention and Market Failures
    Sometimes markets fail to allocate resources efficiently, such as in the presence of externalities like pollution.
    Public policies, regulations, and corrective Pigouvian taxes can alter incentives and improve social welfare.
    """
    chapters = MaterialParser.detect_outline_or_chapters(sample_text)
    assert len(chapters) == 3
    assert "Classical Economics" in chapters[0]["title"]
    assert "Market Equilibrium" in chapters[1]["title"]
    assert "Government Intervention" in chapters[2]["title"]
    assert len(chapters[0]["content"]) > 100


def test_fragment_consolidation():
    # If a sub-section is too brief (<600 chars), it should be merged with preceding section rather than creating a fragmented 1-sentence chapter
    sample_text = """
    Chapter 1: The Nervous System
    The human nervous system is an intricate network of neurons communicating via electrical and chemical impulses.
    Sensory receptors capture external inputs and transmit action potentials along afferent pathways to the spinal cord and brain.
    
    Section 1.1: Synaptic Cleft
    Synapses use neurotransmitters to bridge gaps.
    
    Chapter 2: The Endocrine System
    Hormones act as slow-acting chemical messengers secreted by ductless glands directly into the circulatory bloodstream.
    Target organs possess specific receptor proteins that bind corresponding hormones to regulate physiological homeostasis.
    """
    chapters = MaterialParser.detect_outline_or_chapters(sample_text)
    assert len(chapters) == 2
    assert "Chapter 1" in chapters[0]["title"]
    assert "Synapses use neurotransmitters" in chapters[0]["content"]  # Consolidated
    assert "Chapter 2" in chapters[1]["title"]


def test_continuous_text_cognitive_sizing():
    # Continuous text without headings should be partitioned into cognitively sized sections
    paragraphs = [
        f"Paragraph {i}: In the continuous study of thermodynamic transformations, work and heat exchange represent the two path-dependent modes of energy transfer across system boundaries. State functions such as internal energy, enthalpy, and entropy describe equilibrium states independently of the path taken. When irreversible phenomena occur, entropy generation measures the degree of thermodynamic degradation."
        for i in range(25)
    ]
    long_continuous_text = "\n\n".join(paragraphs)
    chapters = MaterialParser.detect_outline_or_chapters(long_continuous_text)
    assert len(chapters) >= 2
    for ch in chapters:
        # Cognitively manageable size
        assert len(ch["content"]) >= 1500
        assert ch["title"].startswith("Section ")
