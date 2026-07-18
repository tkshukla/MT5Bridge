//+------------------------------------------------------------------+
//| JsonHelper.mqh                                                    |
//| Minimal, purpose-built JSON value extraction for MT5Bridge.       |
//| This is NOT a general-purpose JSON parser: it assumes flat JSON   |
//| objects (string/number/bool/null values only, no nested objects   |
//| in the fields it reads) which matches every response shape this   |
//| API actually returns to MT5. Do not reuse for arbitrary JSON.     |
//+------------------------------------------------------------------+
#property strict

//--- Find the raw substring value (still containing quotes if a string) for "key":value
string JsonRawValue(const string &json, const string key)
  {
   string needle = "\"" + key + "\"";
   int key_pos = StringFind(json, needle);
   if(key_pos < 0)
      return "";

   int colon_pos = StringFind(json, ":", key_pos + StringLen(needle));
   if(colon_pos < 0)
      return "";

   int i = colon_pos + 1;
   int len = StringLen(json);

   // skip whitespace
   while(i < len && (StringGetCharacter(json, i) == ' ' || StringGetCharacter(json, i) == '\t'))
      i++;

   if(i >= len)
      return "";

   ushort first_char = StringGetCharacter(json, i);

   if(first_char == '"')
     {
      int start = i + 1;
      int j = start;
      while(j < len)
        {
         ushort c = StringGetCharacter(json, j);
         if(c == '\\')
           {
            j += 2;
            continue;
           }
         if(c == '"')
            break;
         j++;
        }
      return StringSubstr(json, start, j - start);
     }

   // number / bool / null literal — read until , } or ]
   int start = i;
   int j = i;
   while(j < len)
     {
      ushort c = StringGetCharacter(json, j);
      if(c == ',' || c == '}' || c == ']')
         break;
      j++;
     }
   string raw = StringSubstr(json, start, j - start);
   StringTrimLeft(raw);
   StringTrimRight(raw);
   return raw;
  }

string JsonGetString(const string &json, const string key)
  {
   return JsonRawValue(json, key);
  }

double JsonGetDouble(const string &json, const string key, double default_value = 0.0)
  {
   string raw = JsonRawValue(json, key);
   if(raw == "" || raw == "null")
      return default_value;
   return StringToDouble(raw);
  }

long JsonGetLong(const string &json, const string key, long default_value = 0)
  {
   string raw = JsonRawValue(json, key);
   if(raw == "" || raw == "null")
      return default_value;
   return StringToInteger(raw);
  }

bool JsonGetBool(const string &json, const string key, bool default_value = false)
  {
   string raw = JsonRawValue(json, key);
   if(raw == "true")
      return true;
   if(raw == "false")
      return false;
   return default_value;
  }

//--- Split a top-level JSON array of objects ("[{...},{...}]") into individual
//--- object substrings ("{...}"), respecting brace/bracket/string nesting.
int JsonSplitArrayObjects(const string &json_array, string &out_objects[])
  {
   int len = StringLen(json_array);
   int start_bracket = StringFind(json_array, "[");
   if(start_bracket < 0)
     {
      ArrayResize(out_objects, 0);
      return 0;
     }

   int depth = 0;
   int obj_start = -1;
   bool in_string = false;
   int count = 0;
   ArrayResize(out_objects, 0);

   for(int i = start_bracket; i < len; i++)
     {
      ushort c = StringGetCharacter(json_array, i);

      if(in_string)
        {
         if(c == '\\')
           {
            i++; // skip escaped char
            continue;
           }
         if(c == '"')
            in_string = false;
         continue;
        }

      if(c == '"')
        {
         in_string = true;
         continue;
        }
      if(c == '{')
        {
         if(depth == 0)
            obj_start = i;
         depth++;
        }
      else if(c == '}')
        {
         depth--;
         if(depth == 0 && obj_start >= 0)
           {
            count++;
            ArrayResize(out_objects, count);
            out_objects[count - 1] = StringSubstr(json_array, obj_start, i - obj_start + 1);
            obj_start = -1;
           }
        }
     }
   return count;
  }
