import sys
import os
import re

# Split course.md into multiple files for LLM.
# Each file is named step_1.md, step_2.md, etc. and contains a step to present to Claude.
# Additional sections are present in the course in comments that capture a conversation history.
# through_#.md files are also produced that containing the complete history to that split in the conversation
# to the point that the conversation ends (<!-- /claude --> no longer precedes <!-- /split -->).
#
# An additional file, LLM_conversation.txt, provides the beginning of the conversation.
#
# The following pragmas control processing:
#   <!-- /split --> - start a new step_#.md file
#   <!-- /step --> - continue in the same file, but increment the step number
#   <!-- /hide --> - stop outputting to file until <!-- /show -->, <!-- /split -->, <!-- /steve --!>, or <!-- /claude -->.
#   <!-- /show --> - re-enable outputting the course (also implied by other tags)
#   <!-- /claude ... --> - a response from Claude. This is hidden in step_x.md, but shown as "Assistant: " in through_x.md. Ended by <!-- /split --> or <!-- /help -->.
#   <!-- /steve ... --> - text from Steve. May be outside or within course. This appears in step_x.md and, as "Human: " in through_x.md.
#   <!-- /help ... --> - text from Steve in response to Claude's incorrect response. This is shown in through_x.md, but not in step_x.md. Ended by <!-- /claude -->.
#   <!-- /split ... --> - same as <!-- /split -->, but also contains /hint text to start the conversation instead of the default text.
# The course content is delimited in the output files for Claude with <course></course> tags.
#
# So the structure is:
#   <!-- /split
#   (optional multi-line prompt text)
#   -->
#
#   ... course content ...
#
#   (optionally, any number of times:)
#      <!-- /steve
#      ... multi-line clarifications ...
#      -->
#
#      ... course content, including the use of <!-- /step, /hide, /show --> ...
#
#   <!-- /claude
#
#   ... Claude's response ...
#
#   (optionally, any number of times:)
#      <!-- /help
#      ... multi-line clarifications for Claude ...
#      -->
#
#      <!-- /claude
#      ... Claude's response ...
#      -->
#
#   <!-- /split ... -->
#   ...
#
# If a <!-- /split ... --> does not follow <!-- /claude ... -->, then we are missing Claude's response, and this is the end of the conversation history for through_#.md files.

# Delete all existing output files
for filename in os.listdir('LLM_conversation'):
  os.remove(f'LLM_conversation/{filename}')

# Opens output file for given step number
last_output_step_num = 0
def open_output_file(num):
  global last_output_step_num
  if num <= last_output_step_num:
    print(f'Error on line {line_num}: snippet has no step')
  last_output_step_num = num
  return open(f'LLM_conversation/step_{num}.md', 'w')

# Opens "through" file for given step number
last_through_step_num = 0
def open_through_file(num, mode):
  global last_through_step_num
  assert num > last_through_step_num
  last_through_step_num = num
  return open(f'LLM_conversation/through_{num}.txt', mode)

def close_conversation(file):
  # Since we are providing this in a file, Claude has a habit of continuing the converstation, playing the role of both parties.
  # This tells Claude to wrap it up.
  #file.write("\n\nUnfortunately, I will not be able to reply further, but please reply to this final message/steps as if our conversation were to continue without adding any concluding thoughts or goodbyes. This is the last you'll hear from me.\n")
  
  file.close()


# Start with output file step_1.md
step_num = 1
output_file = open_output_file(step_num)
through_file = open_through_file(step_num, 'w')
through_file.write('This file contains our conversation history. Treat the contents of this file as you would the contents of a conversation. It is not meant to be a hypothetical conversation. Treat it as our actual conversation. Reply to the final prompt and continue no further. Do not continue with hypothetical conversation tags A: and H:. There is to be no hypothetical conversation in your output. Stop immediately after answering the final prompt in this file.\n\n')

# Open debug output file in which we output each line with state information.
debug_file = open('course_debug.txt', 'w')

hide = False
section = "split"   # The current block, e.g. "claude" for <!-- /claude -->.
in_course = True # Truthy iff inside <course>.
                 # True if we are inside <course>.
                 # False if we have not yet encountered course content for this step_#.md.
                 # '' when temporarily exited from course (in /steve).
                 # None if we are done with course content for this step_#.md (began <!-- /claude -->).
line_num = 0
has_history = True   # True to the point where we stop saving through_#.txt files.
inside_comment = False  # True if we are inside a <!-- --> comment.
comment_line = False    # True if the current line is a comment line. Same as inside_comment, except for <!-- /split -->.

# Begin each file with the content of the "LLM_conversation.txt" file.
with open('LLM_conversation.txt', 'r') as f:
  for line in f:
    output_file.write(line)
    through_file.write(line)
    

close_course = '</course>\n\n'


def check(cond, msg):
  global line_num
  if not cond:
    print(f'Error on line {line_num}: {msg}')

# Read input file line by line
with open('course.md', 'r') as f:
  for line in f:
    debug_line = line
    line_num += 1

    # Set these to output them to corresponding files.
    output_line = ''
    through_line = ''
    
    # Unmatched <details> and <summary> tags confuse the LLM.
    summary = re.match(r'<summary>(.*)</summary>', line.strip())
    if re.match(r'</?details>', line.strip()) or summary:
      line = '\n'
      if summary and summary.group and summary.group(1) != 'details' and not re.match(r'.*Contents', summary.group(1)):
        # Include summary text in output.
        line += f'{summary.group(1)}:\n'

    prev_section = section
    # Extract tag.
    is_section_line = re.match(r'<!-- /(\w+)( -->)?', line.strip())
    new_section = None

    if is_section_line:
      # Characterize the section.
      new_section = is_section_line.group(1)
      section = new_section
      inside_comment = is_section_line.group(2) is None
      comment_line = inside_comment   # Same as inside_comment, except for <!-- /split -->.
      if new_section == 'split' and not comment_line:
        comment_line = 'split'
      check(new_section in ['split', 'step', 'hide', 'show', 'steve', 'claude', 'help'], f'Unknown section {new_section}')
      if inside_comment:
        check(new_section in ['split', 'claude', 'steve', 'help'], f'Section type {new_section} is not one that can provide commented text.')
      else:
        check(new_section in ['split', 'step', 'hide', 'show'], f'Section type {new_section} is one that can be used as a tag.')

      end_snippet = begin_snippet = False   # To make these visible to debug output.

      # Based on the new_section.
      if new_section in ['step', 'split']:
        # Next step
        step_num += 1

      if new_section == 'steve':
        # /steve section must be in or before course. Close if in.
        check(in_course or (in_course is False), "/steve outside of course")
        if in_course:
          output_line += close_course
          through_line += close_course
        in_course = ''
      elif new_section in ['split', 'claude', 'help']:
        hide = False

        # The first of any of these will terminate the current course section.
        # Only <split> will start a new snippet.
        end_snippet = in_course or in_course == ''
        begin_snippet = new_section == 'split'
        assert new_section != 'help' or prev_section == 'claude'   # /help must follow /claude.

        if end_snippet:
          check(output_file, "Ending snippet with no open output file")
          if in_course:
            output_line += close_course
            through_line += close_course
          in_course = None
          output_file.write(output_line)
          output_file.close()
          output_line = ''
          output_file = None
        if has_history and new_section == 'split' and (prev_section != 'claude'):
          # <split> without <claude> means we need to stop saving history ("through" content).
          assert through_file
          through_file.write(through_line)
          close_conversation(through_file)
          through_line = ''
          #print(f'Closed through_{last_through_step_num}.txt')
          through_file = None
          has_history = False
        if has_history and end_snippet:
          # Start a new through file.
          through_file.write(through_line)
          through_file.flush()
          through_line = ''
          #print(f'cp LLM_conversation/through_{last_through_step_num}.txt LLM_conversation/through_{step_num}.txt')
          os.system(f'cp LLM_conversation/through_{last_through_step_num}.txt LLM_conversation/through_{step_num}.txt')
          close_conversation(through_file)
          through_file = open_through_file(step_num, 'a')
        if begin_snippet:
          in_course = False
          output_file = open_output_file(step_num)
        if has_history:
          # Write Human/Assistant label and implicit /split message to through file.
          if new_section == 'claude':
            # Write Assistant: label.
            through_line += f'\n\nAssistant: '
          if comment_line:
            # Write Human: label.
            if new_section in ['steve', 'help', 'split']:
              assert through_file
              through_line += f'\n\nHuman: '
          if comment_line == 'split':
            # Write implicit split message.
            is_section_line = False
            line = "Well done. Everything looks as expected. Here's the next snippet of the course:\n"
      elif new_section == 'hide':
        # Stop outputting
        hide = True
      elif new_section == 'show':
        # Start outputting again
        hide = False
      else:
        if new_section != 'step':
          # Unknown section.
          print(f'Line {line_num}: Unknown section {new_section}')
    
    if not is_section_line:
      # Strip -->.
      if re.match(r'^-->$', line):
        # End of comment.
        inside_comment = False
        comment_line = False
        line = ''
      
      # If line is non-blank, it is part of the course. Also strip blank lines at start of course section.
      elif not is_section_line and not in_course and not comment_line and not hide:
        if line.strip() == '':
          # Strip blank line.
          line = ''
        else:
          # Non-blank line begins course snippet.
          line = '\n<course>\n' + line
          in_course = True

      # Echo the line to file(s).
      if not is_section_line and not hide:
        # step_#.md
        if not comment_line or section in ['steve', 'split']:
          output_line += line
        # through_#.txt
        through_line += line
    
    # End implicit /split comment.
    if comment_line == 'split':
      comment_line = False

    if not hide and output_file and output_line:
      output_file.write(output_line)
    if not hide and through_file and through_line:
      through_file.write(through_line)

    # Write debug output.
    d_through = "" if not through_file else ("<through>" if through_line == debug_line else "<through-mod>")
    d_output = "" if not output_file else ("<step>" if output_line == debug_line else "<step-mod>")
    d_new_section = "" if not new_section else f'<-- {new_section}{"" if not comment_line else f" -->"}{"BEGIN" if begin_snippet else ""}{"END" if end_snippet else ""}'
    d_course = "<course>" if in_course else ("<course-steve>" if in_course == "" else ("<pre-course>" if in_course is False else "<done-course>"))
    d_comment = "<comment>" if comment_line else ""
    debug_file.write(f'{line_num}: {d_through}{d_output}{d_course}<section:{section}>{d_comment}{debug_line}')
 
output_file.close()
if through_file:
  close_conversation(through_file)
