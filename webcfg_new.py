import logging
import json
import toml
import _thread
import pwnagotchi
from pwnagotchi import restart, plugins
from pwnagotchi.utils import save_config, merge_config
from flask import abort
from flask import render_template_string

# MODIFIED INDEX TEMPLATE STRING STARTS HERE
INDEX = """
{% extends "base.html" %}
{% set active_page = "plugins" %}
{% block title %}
    webcfg2
{% endblock %}

{% block meta %}
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, user-scalable=0" />
{% endblock %}

{% block styles %}
{{ super() }}
<style>
    /* --- Existing styles --- */
    #divTop {
        position: -webkit-sticky;
        position: sticky;
        top: 0px;
        width: 100%;
        font-size: 16px;
        padding: 5px;
        border: 1px solid #ddd;
        margin-bottom: 5px;
        background-color: #f8f8f8; /* Added background for visibility */
        z-index: 10; /* Ensure it stays on top */
    }

    #searchText {
        width: 100%;
        padding: 5px;
        box-sizing: border-box; /* Include padding in width */
    }

     #selAddType {
        padding: 5px;
        margin-left: 5px;
        height: 30px; /* Match button height roughly */
        vertical-align: middle;
    }

    #btnAdd {
        padding: 5px 10px;
        margin-left: 5px;
        cursor: pointer;
        height: 30px; /* Match select height roughly */
        vertical-align: middle;
    }

    table {
        table-layout: auto;
        width: 100%;
        margin-top: 5px; /* Add space below sticky header */
    }

    table, th, td {
      border: 1px solid black;
      border-collapse: collapse;
    }

    th, td {
      padding: 15px;
      text-align: left;
      vertical-align: middle; /* Align content vertically */
    }

    table tr:nth-child(even) {
      background-color: #eee;
    }

    table tr:nth-child(odd) {
     background-color: #fff;
    }

    table th {
      background-color: black;
      color: white;
    }

    .remove {
        background-color: #f44336;
        color: white;
        border: 2px solid #f44336;
        padding: 4px 8px;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 12px;
        margin: 0; /* Removed margin */
        -webkit-transition-duration: 0.4s; /* Safari */
        transition-duration: 0.4s;
        cursor: pointer;
        vertical-align: middle;
    }

    .remove:hover {
        background-color: white;
        color: black;
    }

     #divSaveButtons { /* Changed ID for clarity */
        position: -webkit-sticky;
        position: sticky;
        bottom: 0px;
        width: 100%;
        background-color: #f8f8f8; /* Added background for visibility */
        padding: 10px 0; /* Add padding */
        border-top: 1px solid #ddd; /* Add separator */
        text-align: right; /* Align buttons right */
        z-index: 10; /* Ensure it stays on top */
    }

    #btnSave, #btnMergeSave { /* Target both buttons */
        background-color: #0061b0;
        border: none;
        color: white;
        padding: 10px 20px; /* Adjusted padding */
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 14px; /* Adjusted font size */
        cursor: pointer;
        margin-left: 10px; /* Add space between buttons */
    }
    #btnMergeSave {
        background-color: #ff8c00; /* Different color for caution */
    }


    #divTop {
        display: table;
        width: 100%;
        box-sizing: border-box; /* Include padding in width */
    }
    #divTop > * {
        display: table-cell;
        vertical-align: middle; /* Align items vertically */
    }
    #divTop > span { /* Target the spans holding select and button */
       white-space: nowrap; /* Prevent wrapping */
       width: 1%; /* Let input take most space */
    }
    #divTop > input {
        width: 100%;
    }

    @media screen and (max-width:700px) {
        /* --- Existing media query styles --- */
        table, tr, td {
            padding:0;
            border:1px solid black;
        }

        table {
            border:none;
        }

        tr:first-child, thead, th {
            display:none;
            border:none;
        }

        tr {
            float: left;
            width: 100%;
            margin-bottom: 2em;
        }

        table tr:nth-child(odd) {
            background-color: #eee;
        }

        td {
            float: left;
            width: 100%;
            padding:1em;
            box-sizing: border-box; /* Add box-sizing */
        }

        td::before {
            content:attr(data-label);
            word-wrap: break-word;
            background: #eee;
            border-right:2px solid black;
            width: 20%;
            float:left;
            padding:1em;
            font-weight: bold;
            margin:-1em 1em -1em -1em;
            box-sizing: border-box; /* Add box-sizing */
        }

        .del_btn_wrapper { /* Make sure button wrapper behaves well */
           /* --- Keep previous styles or adjust as needed --- */
           content:attr(data-label); /* This seems wrong, remove if it was copy-paste error */
            word-wrap: break-word;
            background: #eee;
            border-right:2px solid black;
            width: 20%;
            float:left;
            padding:1em;
            font-weight: bold;
            margin:-1em 1em -1em -1em;
            box-sizing: border-box; /* Add box-sizing */
        }

        #divTop {
            display: block; /* Stack elements vertically */
        }
        #divTop > * {
            display: block; /* Stack elements vertically */
            width: 100%; /* Make elements full width */
            margin-bottom: 5px; /* Add space between elements */
        }
         #divTop > span {
             width: 100%; /* Make span full width */
             display: flex; /* Use flex to place select and button side-by-side */
             justify-content: space-between; /* Space them out */
         }
          #selAddType {
             flex-grow: 1; /* Let select grow */
             margin-left: 0; /* Remove left margin */
             margin-right: 5px; /* Add right margin */
         }
         #btnAdd {
             margin-left: 0; /* Remove left margin */
         }

          #divSaveButtons {
             text-align: center; /* Center buttons on small screens */
         }
         #btnSave, #btnMergeSave {
             display: block; /* Stack buttons */
             width: 90%; /* Make buttons wide */
             margin: 5px auto; /* Center buttons and add space */
         }
    }
</style>
{% endblock %}

{% block content %}
    <div id="divTop">
        <input type="text" id="searchText" placeholder="Search or enter new option name ..." title="Type an option name">
        <span> <select id="selAddType">
                <option value="text">Text</option>
                <option value="number">Number</option>
                <option value="boolean">Boolean</option> </select>
            <button id="btnAdd" type="button" onclick="addOption()">+</button>
        </span>
    </div>
    <div id="divSaveButtons"> <button id="btnMergeSave" type="button" onclick="saveConfigNoRestart()">Merge and Save (CAUTION)</button> <button id="btnSave" type="button" onclick="saveConfig()">Save and restart</button> </div>
    <div id="content"></div>
{% endblock %}

{% block script %}
        function addOption() {
          var valueInput, table, tr, td, divDelBtn, btnDel, selType, selTypeVal, optionKeyInput, optionKey; // Declared variables
          optionKeyInput = document.getElementById("searchText"); // Input field for the option key
          optionKey = optionKeyInput.value.trim(); // Get the option key, trim whitespace

          if (!optionKey) { // Prevent adding empty keys
              alert("Please enter an option name.");
              optionKeyInput.focus();
              return;
          }

          // Check for dots in the key name, which might interfere with flatten/unflatten logic if not intended
          if (optionKey.includes('.')) {
              if (!confirm("Option names with '.' create nested structures (e.g., 'main.plugins').\nAre you sure you want to use '.' in the name '" + optionKey + "'?")) {
                  optionKeyInput.focus();
                  return;
              }
          }


          selType = document.getElementById("selAddType");
          selTypeVal = selType.options[selType.selectedIndex].value;
          table = document.getElementById("tableOptions");

          if (table) {
            // --- Check if key already exists ---
            var existingKeys = table.querySelectorAll('td[data-label="Option"]');
            for (var i = 0; i < existingKeys.length; i++) {
                if (existingKeys[i].textContent.trim() === optionKey) {
                    alert("Option '" + optionKey + "' already exists in the table. Edit the existing one or delete it first.");
                    // Highlight existing row (optional)
                     existingKeys[i].parentNode.style.backgroundColor = "#ffcccc";
                     setTimeout(function(){ existingKeys[i].parentNode.style.backgroundColor = ""; }, 2000); // Reset color after 2s
                     optionKeyInput.focus();
                    return;
                }
            }
            // --- End check ---

            tr = table.insertRow(-1); // Insert at the end
            // del button
            divDelBtn = document.createElement("div");
            divDelBtn.className = "del_btn_wrapper";
            td = document.createElement("td");
            td.setAttribute("data-label", "");
            btnDel = document.createElement("Button");
            btnDel.innerHTML = "X";
            btnDel.onclick = function(){ delRow(this);};
            btnDel.className = "remove";
            divDelBtn.appendChild(btnDel);
            td.appendChild(divDelBtn);
            tr.appendChild(td);
            // option (key)
            td = document.createElement("td");
            td.setAttribute("data-label", "Option");
            td.innerHTML = optionKey; // Use the entered option key
            tr.appendChild(td);
            // value (input element based on type)
            td = document.createElement("td");
            td.setAttribute("data-label", "Value");

            // --- *** MODIFIED PART TO HANDLE BOOLEAN *** ---
            if (selTypeVal === 'boolean') {
                // Create a select dropdown for boolean
                valueInput = document.createElement("select"); // Use 'valueInput' for the element holding the value
                var tvalue = document.createElement("option");
                tvalue.setAttribute("value", "true");
                tvalue.appendChild(document.createTextNode("True"));
                var fvalue = document.createElement("option");
                fvalue.setAttribute("value", "false");
                fvalue.appendChild(document.createTextNode("False"));
                valueInput.appendChild(tvalue);
                valueInput.appendChild(fvalue);
                valueInput.value = "true"; // Default to true
            } else if (selTypeVal === 'number') {
                // Existing logic for number
                 valueInput = document.createElement("input");
                 valueInput.type = 'number';
                 valueInput.value = "0"; // Default number to 0
                 valueInput.setAttribute("step", "any"); // Allow decimals for number type
            } else { // Default to 'text'
                // Existing logic for text
                valueInput = document.createElement("input");
                valueInput.type = 'text';
                valueInput.value = ""; // Default text to empty
            }
            td.appendChild(valueInput); // Append the created element (input or select)
            // --- *** END MODIFIED PART *** ---

            tr.appendChild(td); // Append the value cell to the row

            optionKeyInput.value = ""; // Clear the search/add input field
            optionKeyInput.focus(); // Set focus back to input for next entry
            // Scroll the new row into view (optional)
            tr.scrollIntoView({ behavior: 'smooth', block: 'center' });


          } else {
              alert("Error: Could not find the options table.");
          }
        }

        function saveConfig(){
            var table = document.getElementById("tableOptions");
            if (table) {
                var json = tableToJson(table);
                console.log("Saving Config:", JSON.stringify(json, null, 2)); // Debug output
                sendJSON("webcfg2/save-config", json, function(response) {
                    if (response) {
                        if (response.status == "200") {
                            alert("Config saved successfully. Pwnagotchi will restart.");
                            // Optionally disable buttons or show a loading indicator here
                        } else {
                            alert("Error while saving the config (HTTP Status: " + response.status + "). Check Pwnagotchi logs for details.\nResponse: " + response.responseText);
                        }
                    } else {
                        alert("No response received from server. Check Pwnagotchi status and network connection.");
                    }
                });
            } else {
                 alert("Error: Could not find the options table to save.");
            }
        }

        function saveConfigNoRestart(){
            var table = document.getElementById("tableOptions");
            if (table) {
                var json = tableToJson(table);
                 console.log("Merging/Saving Config:", JSON.stringify(json, null, 2)); // Debug output
                sendJSON("webcfg2/merge-save-config", json, function(response) {
                    if (response) {
                         if (response.status == "200") {
                            alert("Config merged and saved successfully. Restart Pwnagotchi manually for all changes to take full effect.");
                            // Reload the table to reflect potentially merged values from backend
                            loadConfigTable();
                        } else {
                             alert("Error while merging/saving the config (HTTP Status: " + response.status + "). Check Pwnagotchi logs for details.\nResponse: " + response.responseText);
                        }
                    } else {
                        alert("No response received from server. Check Pwnagotchi status and network connection.");
                    }
                });
            } else {
                 alert("Error: Could not find the options table to save.");
            }
        }

        var searchInput = document.getElementById("searchText");
        searchInput.onkeyup = function(event) { // Added event parameter
             // Allow adding with Enter key if input has focus and text is entered
             if (event.key === "Enter" && searchInput.value.trim() !== "") {
                addOption();
                return; // Prevent default form submission if applicable
            }

            var filter, table, tr, td, i, txtValue;
            filter = searchInput.value.toUpperCase();
            table = document.getElementById("tableOptions");
            if (table) {
                tr = table.getElementsByTagName("tr");

                // Start loop from 1 to skip header row
                for (i = 1; i < tr.length; i++) {
                    td = tr[i].getElementsByTagName("td")[1]; // Index 1 is the 'Option' column
                    if (td) {
                        txtValue = td.textContent || td.innerText;
                        if (txtValue.toUpperCase().indexOf(filter) > -1) {
                            tr[i].style.display = "";
                        } else {
                            tr[i].style.display = "none";
                        }
                    }
                }
            }
        }

        function sendJSON(url, data, callback) {
          var xobj = new XMLHttpRequest();
          var csrf = "{{ csrf_token() }}";
          xobj.open('POST', url);
          xobj.setRequestHeader("Content-Type", "application/json");
          xobj.setRequestHeader('x-csrf-token', csrf); // Ensure CSRF token is handled if Flask-WTF is used
          xobj.onreadystatechange = function () {
                if (xobj.readyState == 4) { // Request finished
                  callback(xobj); // Pass the whole object for status checking
                }
          };
           xobj.onerror = function () { // Handle network errors
                alert("Network error occurred while sending data to " + url);
                callback(null); // Indicate error to callback
            };
          xobj.send(JSON.stringify(data));
        }

        function loadJSON(url, callback) {
          var xobj = new XMLHttpRequest();
          // xobj.overrideMimeType("application/json"); // Usually not needed, server should send correct type
          xobj.open('GET', url, true);
          xobj.onreadystatechange = function () {
                if (xobj.readyState == 4) { // Request finished
                    if (xobj.status == "200") { // Success
                        try {
                           callback(JSON.parse(xobj.responseText));
                        } catch (e) {
                            console.error("Error parsing JSON response:", e);
                            console.error("Received text:", xobj.responseText);
                            alert("Error parsing configuration data received from the server.");
                        }
                    } else { // Error
                         console.error("Error loading config: HTTP Status " + xobj.status);
                         alert("Error loading configuration from server (HTTP Status: " + xobj.status + "). Check Pwnagotchi logs.");
                    }
                }
          };
          xobj.onerror = function () { // Handle network errors
                console.error("Network error occurred while fetching data from " + url);
                alert("Network error occurred while loading configuration. Check Pwnagotchi status and network connection.");
          };
          xobj.send(null);
        }

        // https://stackoverflow.com/questions/19098797/fastest-way-to-flatten-un-flatten-nested-json-objects
        // Adjusted to handle arrays starting with '#' correctly
        function unFlattenJson(data) {
            "use strict";
            if (Object(data) !== data || Array.isArray(data))
                return data;
            var result = {}, cur, prop, idx, last, temp, use_array;
            for(var p in data) {
                cur = result, prop = "", last = 0;
                do {
                    idx = p.indexOf(".", last);
                    temp = p.substring(last, idx !== -1 ? idx : undefined);
                    // Check if the *next* level should be an array
                    use_array = (idx !== -1 && p.substring(idx + 1).startsWith('#')) || (!isNaN(parseInt(temp)) && cur instanceof Array); // Improved array detection

                    // If current level is an empty object {}, check if it should be an array []
                     if (cur[prop] && Object.keys(cur[prop]).length === 0 && !(cur[prop] instanceof Array) && use_array) {
                         cur[prop] = [];
                     }

                    cur = cur[prop] || (cur[prop] = (use_array ? [] : {}));

                    // If the key itself is numeric (and we are in an array context), use it as index
                    if (!isNaN(parseInt(temp)) && cur instanceof Array) {
                        prop = parseInt(temp);
                    } else {
                        prop = temp;
                    }

                    last = idx + 1;
                } while(idx >= 0);

                 // Handle boolean strings explicitly
                 if (data[p] === 'true') {
                    cur[prop] = true;
                 } else if (data[p] === 'false') {
                    cur[prop] = false;
                 } else {
                    cur[prop] = data[p];
                 }
            }
            // The root key might be empty string "" or the first part of the path if no dots were used
            return result[""] || result;
        }


        function flattenJson(data) {
            var result = {};
            function recurse (cur, prop) {
                if (Object(cur) !== cur) { // Base case: value is primitive
                    result[prop] = cur;
                } else if (Array.isArray(cur)) {
                     // Use index directly for arrays, not '#index'
                     for(var i=0, l=cur.length; i<l; i++) {
                         recurse(cur[i], prop ? prop+"."+i : ""+i);
                     }
                    if (l == 0 && prop) // Represent empty array only if it's not the root
                        result[prop] = [];
                } else { // Value is an object
                    var isEmpty = true;
                    for (var p in cur) {
                        isEmpty = false;
                        recurse(cur[p], prop ? prop+"."+p : p);
                    }
                    if (isEmpty && prop) // Represent empty object only if it's not the root
                        result[prop] = {};
                }
            }
            recurse(data, "");
            // Filter out the root empty object/array representation if nothing was flattened
            if (result[""] && (Object.keys(result[""]).length === 0 || result[""].length === 0) && Object.keys(result).length === 1) {
                 return {}; // Return empty object if original data was empty {} or []
            }
            // Remove the artificial root key if it exists and is empty/array
            if (result.hasOwnProperty("") && (typeof result[""] === 'object' || Array.isArray(result[""])) ) {
                 delete result[""];
            }

            return result;
        }

        function delRow(btn) {
            var tr = btn.closest('tr'); // More robust way to find parent row
            if (tr) {
                 tr.parentNode.removeChild(tr);
            } else {
                console.error("Could not find table row for delete button.");
            }
        }

        function jsonToTable(json) {
            var table = document.createElement("table");
            table.id = "tableOptions";

            // create header
            var tr = table.insertRow();
            var thDel = document.createElement("th");
            thDel.innerHTML = "Del"; // Add header text
            var thOpt = document.createElement("th");
            thOpt.innerHTML = "Option";
            var thVal = document.createElement("th");
            thVal.innerHTML = "Value";
            tr.appendChild(thDel);
            tr.appendChild(thOpt);
            tr.appendChild(thVal);

            var td, divDelBtn, btnDel, valueInput; // Declare valueInput here
            // iterate over keys, sorting them for consistent order
            var sortedKeys = Object.keys(json).sort();

            sortedKeys.forEach(function(key) {
                tr = table.insertRow();
                // del button
                divDelBtn = document.createElement("div");
                divDelBtn.className = "del_btn_wrapper"; // Keep this class if media query uses it
                td = document.createElement("td");
                td.setAttribute("data-label", "Del"); // Match header
                btnDel = document.createElement("Button");
                btnDel.innerHTML = "X";
                btnDel.onclick = function(){ delRow(this);};
                btnDel.className = "remove";
                // divDelBtn.appendChild(btnDel); // Don't wrap if not needed by styles
                td.appendChild(btnDel); // Append directly if wrapper not needed
                tr.appendChild(td);
                // option
                td = document.createElement("td");
                td.setAttribute("data-label", "Option");
                td.innerHTML = key;
                tr.appendChild(td);
                // value
                td = document.createElement("td");
                td.setAttribute("data-label", "Value");

                var value = json[key]; // Get the value for the current key

                // Check value type to create appropriate input/select
                 if(typeof(value)==='boolean'){
                    valueInput = document.createElement("select");
                    // valueInput.setAttribute("id", "boolSelect_" + key.replace(/\./g, '_')); // Unique ID (optional)
                    var tvalue = document.createElement("option");
                    tvalue.setAttribute("value", "true");
                    tvalue.appendChild(document.createTextNode("True"));
                    var fvalue = document.createElement("option");
                    fvalue.setAttribute("value", "false");
                    fvalue.appendChild(document.createTextNode("False"));
                    valueInput.appendChild(tvalue);
                    valueInput.appendChild(fvalue);
                    valueInput.value = String(value); // Set selected option based on boolean value
                    // document.body.appendChild(input); // DON'T append to body
                } else if (typeof(value) === 'number') {
                     valueInput = document.createElement("input");
                     valueInput.type = 'number';
                     valueInput.value = value;
                     valueInput.setAttribute("step", "any"); // Allow decimals
                } else if (Array.isArray(value)) {
                     valueInput = document.createElement("input");
                     valueInput.type = 'text';
                     try {
                         // Pretty print JSON array/object for better readability
                         valueInput.value = JSON.stringify(value, null, 2);
                     } catch (e) {
                         console.error("Error stringifying array/object for key:", key, e);
                         valueInput.value = '[]'; // Fallback
                     }
                } else if (typeof(value) === 'object' && value !== null) { // Handle nested objects
                     valueInput = document.createElement("input");
                     valueInput.type = 'text';
                      try {
                         // Pretty print JSON array/object for better readability
                         valueInput.value = JSON.stringify(value, null, 2);
                     } catch (e) {
                         console.error("Error stringifying array/object for key:", key, e);
                         valueInput.value = '{}'; // Fallback
                     }
                } else { // Default to text input for strings and other types
                     valueInput = document.createElement("input");
                     valueInput.type = 'text';
                     valueInput.value = value === null ? '' : String(value); // Handle null, convert others to string
                }

                td.appendChild(valueInput); // Append the created input/select
                tr.appendChild(td);
            });

            return table;
        }


       function tableToJson(table) {
            var rows = table.getElementsByTagName("tr");
            var i, td, key, value;
            var flatJson = {}; // Build a flat JSON first

            // Start loop from 1 to skip header row
            for (i = 1; i < rows.length; i++) {
                td = rows[i].getElementsByTagName("td");
                if (td.length == 3) {
                    // td[0] = del button
                    key = (td[1].textContent || td[1].innerText).trim(); // Get key from Option column, trim whitespace
                    if (!key) continue; // Skip rows with no key (shouldn't happen with validation)

                    var valueElement = td[2].querySelector("input, select"); // Find input or select in Value column

                    if (valueElement) {
                        if (valueElement.tagName === "SELECT") { // Boolean dropdown
                            flatJson[key] = (valueElement.value === 'true'); // Convert "true"/"false" string to boolean
                        } else if (valueElement.type === "number") {
                            flatJson[key] = Number(valueElement.value) || 0; // Convert to number, default to 0 if invalid/empty
                        } else if (valueElement.type === "text") {
                             var textValue = valueElement.value.trim();
                             // Try to parse if it looks like JSON array or object
                             if ((textValue.startsWith('[') && textValue.endsWith(']')) || (textValue.startsWith('{') && textValue.endsWith('}'))) {
                                 try {
                                     flatJson[key] = JSON.parse(textValue);
                                 } catch (e) {
                                     // If parsing fails, treat it as a plain string
                                     console.warn("Could not parse JSON string for key '" + key + "', treating as plain text:", textValue, e);
                                     flatJson[key] = textValue;
                                 }
                             } else {
                                 // Treat as plain string
                                 flatJson[key] = textValue;
                             }
                        } else { // Other input types (just in case)
                             flatJson[key] = valueElement.value;
                        }
                    } else {
                        console.warn("No input or select found in value cell for key:", key);
                    }
                } else {
                     console.warn("Skipping table row with unexpected cell count:", rows[i]);
                }
            }
             // Unflatten the collected flat JSON
             // Use the potentially improved unFlattenJson function
            try {
                return unFlattenJson(flatJson);
            } catch(e) {
                console.error("Error during unflattening JSON:", e);
                alert("Error processing configuration structure. Check console for details.");
                return {}; // Return empty object on error
            }
        }

        // Function to load and display the config table
        function loadConfigTable() {
             var divContent = document.getElementById("content");
             divContent.innerHTML = "Loading configuration..."; // Show loading message
             loadJSON("webcfg2/get-config", function(response) {
                if(response) {
                    console.log("Loaded Config:", response); // Debug output
                    var flat_json = flattenJson(response);
                    console.log("Flattened Config:", flat_json); // Debug output
                    var table = jsonToTable(flat_json);
                    divContent.innerHTML = ""; // Clear loading message
                    divContent.appendChild(table);
                } else {
                    divContent.innerHTML = "Failed to load configuration."; // Show error message
                }
            });
        }

        // Initial load when the page is ready
        document.addEventListener('DOMContentLoaded', function() {
             loadConfigTable();
        });
{% endblock %}
"""
# MODIFIED INDEX TEMPLATE STRING ENDS HERE

# --- The rest of the Python Plugin code remains the same ---
def serializer(obj):
    if isinstance(obj, set):
        return list(obj)
    raise TypeError


class WebConfig_new(plugins.Plugin):
    __author__ = '33197631+dadav@users.noreply.github.com and edited by avipars'
    __version__ = '1.0.1' # Incremented version
    __license__ = 'GPL3'
    __description__ = 'This plugin allows the user to make runtime changes to the configuration via a web UI. Added ability to enter boolean values too' # Slightly updated description

    def __init__(self):
        self.ready = False
        self.mode = 'MANU'
        self._agent = None
        self.config = {} # Initialize config

    def on_config_changed(self, config):
        self.config = config
        # Ensure pwnagotchi.config is updated if this plugin loads after main init
        if not pwnagotchi.config or not pwnagotchi.config.get('main', {}).get('name'):
             logging.debug("[webcfg2] pwnagotchi.config seems incomplete on_config_changed, merging current config.")
             pwnagotchi.config = merge_config(config, pwnagotchi.config or {})

        self.ready = True
        logging.debug("[webcfg2] Config loaded and plugin ready.")


    def on_ready(self, agent):
        self._agent = agent
        self.mode = 'MANU' if agent.mode == 'manual' else 'AUTO'
        self.config = agent.config() # Get the most current config from agent
        pwnagotchi.config = agent.config() # Ensure global config is also up-to-date
        logging.info("[webcfg2] Agent ready, mode: %s", agent.mode)
        self.ready = True


    def on_internet_available(self, agent):
        # This might be triggered frequently, perhaps not the best place to update config?
        # Let's keep it simple for now.
        self._agent = agent
        self.mode = 'MANU' if agent.mode == 'manual' else 'AUTO'
        # No config update here unless necessary


    def on_loaded(self):
        """
        Gets called when the plugin gets loaded
        """
        logging.info("webcfg2 plugin loaded.")
        # Config might not be fully available here yet, wait for on_ready or on_config_changed

    def on_webhook(self, path, request):
        """
        Serves the current configuration or handles updates.
        """
        # Use self.config which should be updated by on_config_changed or on_ready
        cfg_to_serve = self.config

        # Fallback or safety check: if self.config seems empty, try agent or global config
        if not cfg_to_serve or not cfg_to_serve.get('main', {}).get('name'):
             logging.warning("[webcfg2] self.config seems empty on webhook request. Trying agent/global config.")
             if self._agent:
                 cfg_to_serve = self._agent.config()
             elif pwnagotchi.config:
                 cfg_to_serve = pwnagotchi.config
             else:
                 logging.error("[webcfg2] Cannot determine config to serve!")
                 return "Error: Configuration not available.", 500

        if not self.ready:
             logging.warning("[webcfg2] Received request before plugin reported ready.")
             # Allow access even if not fully ready, but use potentially incomplete config
             # return "Plugin not ready yet. Please wait.", 503


        # Ensure CSRF token if WTForms is enabled (it usually is for web UI)
        # This requires proper setup in Flask app, assuming it's handled by the main app
        # from flask_wtf.csrf import validate_csrf, CSRFError # Example

        if request.method == "GET":
            if path == "/" or not path:
                # Pass csrf_token() to template if CSRF is used
                # from flask_wtf.csrf import generate_csrf # Example
                # return render_template_string(INDEX, csrf_token=generate_csrf)
                return render_template_string(INDEX) # Assuming CSRF handled by JS or framework extension
            elif path == "get-config":
                try:
                    # Return the internally held config
                    return json.dumps(cfg_to_serve, default=serializer)
                except Exception as e:
                    logging.error("[webcfg2] Error serializing config: %s", e)
                    return "Error serializing configuration.", 500
            else:
                abort(404)

        elif request.method == "POST":
             # CSRF Validation Example (needs proper setup)
             # try:
             #     validate_csrf(request.headers.get('x-csrf-token'))
             # except CSRFError as e:
             #     logging.warning("[webcfg2] CSRF validation failed: %s", e)
             #     abort(400, 'CSRF token missing or invalid.')

             config_path = '/etc/pwnagotchi/config.toml'
             backup_path = '/etc/pwnagotchi/config.toml.bak'

             if path == "save-config":
                try:
                    new_config_data = request.get_json()
                    if not isinstance(new_config_data, dict):
                        raise ValueError("Invalid JSON data received.")

                    logging.info("[webcfg2] Received request to save config and restart.")
                    logging.debug("[webcfg2] New config data: %s", json.dumps(new_config_data, indent=2))

                    # Backup existing config before overwriting (important!)
                    try:
                        import shutil
                        shutil.copyfile(config_path, backup_path)
                        logging.info("[webcfg2] Backed up current config to %s", backup_path)
                    except Exception as backup_err:
                         # Log heavily, but proceed with caution? Or abort? Let's abort for safety.
                         logging.error("[webcfg2] FAILED to backup config file '%s': %s. Aborting save.", config_path, backup_err)
                         return "Config backup failed. Save aborted.", 500


                    # Save the new config (overwrites)
                    save_config(new_config_data, config_path)
                    logging.info("[webcfg2] New config saved to %s", config_path)


                    # Update internal states AFTER saving successfully
                    self.config = new_config_data
                    pwnagotchi.config = new_config_data # Update global immediately
                    if self._agent:
                        self._agent._config = new_config_data # Update agent's immediately

                    logging.info("[webcfg2] Triggering restart in mode: %s", self.mode)
                    # Use a small delay before restart to allow response to be sent
                    _thread.start_new_thread(lambda m: (time.sleep(1), restart(m)), (self.mode,))
                    # restart(self.mode) # This might block the response

                    return json.dumps({"message": "Config saved. Restarting..."}), 200 # Return JSON response

                except Exception as ex:
                    logging.exception("[webcfg2] Error processing save-config request: %s", ex) # Log full traceback
                    return json.dumps({"error": "Failed to save config.", "details": str(ex)}), 500

             elif path == "merge-save-config":
                try:
                    update_data = request.get_json()
                    if not isinstance(update_data, dict):
                        raise ValueError("Invalid JSON data received.")

                    logging.info("[webcfg2] Received request to merge and save config.")
                    logging.debug("[webcfg2] Config update data: %s", json.dumps(update_data, indent=2))

                    # Backup existing config before merging/saving (important!)
                    try:
                        import shutil
                        shutil.copyfile(config_path, backup_path)
                        logging.info("[webcfg2] Backed up current config to %s", backup_path)
                    except Exception as backup_err:
                         logging.error("[webcfg2] FAILED to backup config file '%s': %s. Aborting merge-save.", config_path, backup_err)
                         return "Config backup failed. Merge-save aborted.", 500

                    # Perform the merge using the existing config as the base
                    # Make sure self.config is up-to-date before merging
                    current_config = self.config # Use the plugin's view of the config

                    # Safety check: reload from file if self.config seems wrong? Or trust it? Trust for now.
                    # from pwnagotchi.config import load_config
                    # current_config = load_config({'config': config_path}) # Option to reload fresh

                    merged_config = merge_config(update_data, current_config)
                    logging.debug("[webcfg2] Merged config data: %s", json.dumps(merged_config, indent=2))


                    # Save the *merged* config (overwrites)
                    save_config(merged_config, config_path)
                    logging.info("[webcfg2] Merged config saved to %s", config_path)


                    # Update internal states AFTER saving successfully
                    self.config = merged_config # Update plugin's config
                    pwnagotchi.config = merged_config # Update global config
                    if self._agent:
                        self._agent._config = merged_config # Update agent's config
                        # Optionally, notify the agent or other plugins about the change
                        # self._agent.on_config_changed(merged_config) # If agent has such a method


                    logging.info("[webcfg2] Config merged and saved. Manual restart recommended for full effect.")
                    return json.dumps({"message": "Config merged and saved successfully."}), 200 # Return JSON response

                except Exception as ex:
                    logging.exception("[webcfg2] Error processing merge-save-config request: %s", ex) # Log full traceback
                    return json.dumps({"error": "Failed to merge/save config.", "details": str(ex)}), 500

        abort(404) # If no path/method matched

# Need time for delayed restart thread
import time
