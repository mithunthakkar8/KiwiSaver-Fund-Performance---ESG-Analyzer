import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
import os
from Fisher_Funds import Numeric_Data_PDF_Parser  # Replace with your actual module name

# ========== Fixtures ==========
@pytest.fixture
def sample_parser():
    return Numeric_Data_PDF_Parser(
        folder_path="test_folder",
        terms_to_search=["Test Term"],
        validation_file="test_output.xlsx"
    )

@pytest.fixture
def mock_pdf_document():
    doc = MagicMock()
    page = MagicMock()
    doc.__iter__.return_value = [page]
    return doc

@pytest.fixture
def mock_text_span():
    return {
        "origin": (100, 100),
        "text": "Test Text",
        "size": 12
    }

# ========== Unit Tests ==========
class TestInitialization:
    def test_parser_initialization(self, sample_parser):
        assert sample_parser.folder_path == "test_folder"
        assert sample_parser.terms_to_search == ["Test Term"]
        assert sample_parser.output_excel == os.path.join("test_folder", "test_output.xlsx")
        assert sample_parser.x_tolerance == 20
        assert sample_parser.y_tolerance == 8

class TestFileYearExtraction:
    def test_get_file_year_valid(self, sample_parser):
        assert sample_parser.get_file_year("file_2023.pdf") == 2023
    
    def test_get_file_year_invalid(self, sample_parser):
        assert sample_parser.get_file_year("file.pdf") is None

class TestDBSCANMethods:
    def test_group_spans_empty(self, sample_parser):
        assert sample_parser.group_spans([]) == []
    
    def test_group_spans_single_span(self, sample_parser, mock_text_span):
        result = sample_parser.group_spans([mock_text_span])
        assert len(result) == 1
        assert "Test Text" in result[0][0]
    
    def test_group_spans_multiple_spans(self, sample_parser):
        spans = [
            {"origin": (100, 100), "text": "Header1", "size": 12},
            {"origin": (200, 100), "text": "Header2", "size": 12},
            {"origin": (100, 120), "text": "1", "size": 12},
            {"origin": (200, 120), "text": "100", "size": 12},
        ]
        result = sample_parser.group_spans(spans)
        assert len(result) == 2  # Header row and data row
        assert len(result[0]) == 2  # Two columns
    
    def test_group_spans_with_footer(self, sample_parser):
        spans = [
            {"origin": (100, 100), "text": "Data", "size": 12},
            {"origin": (200, 100), "text": "100", "size": 12},
            {"origin": (100, 500), "text": "currency hedging", "size": 12},
        ]
        result = sample_parser.group_spans(spans)
        assert len(result) == 1  # Should stop before footer
    
    @patch('sklearn.cluster.DBSCAN')
    def test_extract_with_dbscan(self, mock_dbscan, sample_parser, mock_pdf_document):
        mock_page = mock_pdf_document.__iter__.return_value[0]
        mock_page.search_for.return_value = [MagicMock(x0=100, y0=100, x1=200, y1=200)]
        
        mock_block = {
            "blocks": [{
                "lines": [{
                    "spans": [{
                        "bbox": (100, 100, 200, 200),
                        "text": "Test Data",
                        "size": 12
                    }]
                }]
            }]
        }
        mock_page.get_text.return_value = mock_block
        
        result = sample_parser.extract_with_dbscan(mock_pdf_document)
        assert len(result) > 0

class TestCamelotMethods:
    def test_is_data_cell(self, sample_parser):
        assert sample_parser.is_data_cell("100") is True
        assert sample_parser.is_data_cell("100%") is True
        assert sample_parser.is_data_cell("-") is True
        assert sample_parser.is_data_cell("Text") is False
    
    def test_detect_header_row_count(self, sample_parser):
        rows = [
            ["Header1", "Header2"],
            ["1", "100"],
            ["2", "200"]
        ]
        assert sample_parser.detect_header_row_count(rows) == 1
    
    def test_detect_label_column_count(self, sample_parser):
        rows = [
            ["Label", "Value"],
            ["1", "100"],
            ["2", "200"]
        ]
        assert sample_parser.detect_label_column_count(rows, 1) == 1
    
    def test_normalize_table_rows(self, sample_parser):
        rows = [
            ["100", "%"],
            ["200", "300"],
            ["", "400%"]
        ]
        result = sample_parser.normalize_table_rows(rows)
        assert result[0][0] == "100%"
        assert result[1][1] == "300"
        assert result[2][1] == "400%"

class TestCleaningMethods:
    def test_clean_extracted_table_empty(self, sample_parser):
        assert sample_parser.clean_extracted_table([]) == []
    
    def test_clean_extracted_table_remove_terms(self, sample_parser):
        rows = [
            ["Test Term", "100"],
            ["Data", "200"]
        ]
        result = sample_parser.clean_extracted_table(rows)
        assert len(result) == 1
        assert "Test Term" not in result[0]
    
    def test_clean_extracted_table_merge_percent(self, sample_parser):
        rows = [
            ["Value"],
            ["100", "%"],
            ["200", "300"]
        ]
        result = sample_parser.clean_extracted_table(rows)
        assert result[1][0] == "100%"
    
    def test_clean_extracted_table_merge_rows(self, sample_parser):
        rows = [
            ["Label"],
            ["1", ""],
            ["", "100"],
            ["2", "200"]
        ]
        result = sample_parser.clean_extracted_table(rows)
        assert len(result) == 3  # Header + 2 merged rows
        assert result[1][1] == "100"
    
    def test_clean_extracted_table_remove_empty_cols(self, sample_parser):
        rows = [
            ["Label", "", "Value"],
            ["1", "", "100"],
            ["2", "", "200"]
        ]
        result = sample_parser.clean_extracted_table(rows)
        assert len(result[0]) == 2  # Empty column removed
    
    def test_clean_extracted_table_integer_cleaning(self, sample_parser):
        rows = [
            ["ID", "Value"],
            ["1 Text", "100"],
            ["2 More", "200"]
        ]
        result = sample_parser.clean_extracted_table(rows)
        assert result[1][0] == "1"
        assert "Text" in result[1][1]

class TestMainProcessing:
    @patch('your_module.fitz.open')
    @patch('your_module.camelot.read_pdf')
    def test_process_pdf_pre_2024(self, mock_camelot, mock_fitz, sample_parser):
        # Test pre-2024 file (uses DBSCAN)
        mock_doc = MagicMock()
        mock_fitz.return_value = mock_doc
        sample_parser.extract_with_dbscan = MagicMock(return_value=[["Data"]])
        
        result = sample_parser.process_pdf("file_2023.pdf")
        assert result == [["Data"]]
    
    @patch('your_module.camelot.read_pdf')
    def test_process_pdf_2024(self, mock_camelot, sample_parser):
        # Test 2024+ file (uses Camelot)
        mock_table = MagicMock()
        mock_table.df = pd.DataFrame([["Data"]])
        mock_camelot.return_value = [mock_table]
        
        result = sample_parser.process_pdf("file_2024.pdf")
        assert result == [["Data"]]

class TestExportMethods:
    @patch('pandas.DataFrame.to_excel')
    @patch('os.listdir')
    @patch('os.path.join')
    def test_validate_and_export(self, mock_join, mock_listdir, mock_to_excel, sample_parser):
        mock_listdir.return_value = ["test.pdf"]
        sample_parser.process_pdf = MagicMock(return_value=[["Data"]])
        sample_parser.get_file_year = MagicMock(return_value=2023)
        
        sample_parser.validate_and_export()
        mock_to_excel.assert_called_once()