import re

import json


def build_doc_diffs(text_orginal, text_processed):
	"""
	Builds the document diffs between the original and processed text.
	:param text_orginal: The original text.
	:param text_processed: The processed text.
	:return: None
	"""



	text_processed_normalized = text_processed.replace("\n", " ")
	text_processed_normalized = text_processed.replace("\t", " ")
	
	text_orginal_normalized = text_orginal.replace("\n", " ")
	text_orginal_normalized = text_orginal.replace("\t", " ")

	text_processed_normalized = text_processed_normalized.replace("<BLOCKBREAK/>", "")


	all_matches = re.findall(r"{.*?\|[0-9]+\|.*?}", text_processed_normalized)

	for match in all_matches:

		
		word = match.split("|")[0][1:]
		# print(match,word)

		text_processed_normalized = text_processed_normalized.replace(match, word)


	text_processed_normalized = re.sub(r"\s+", " ", text_processed_normalized)
	text_orginal_normalized = re.sub(r"\s+", " ", text_orginal_normalized)

	# text_orginal_normalized = text_orginal_normalized.replace("­-", "-")
	# text_orginal_normalized = text_orginal_normalized.replace("­-", "-")




	text_processed_normalized = text_processed_normalized.replace("- ", "")
	text_orginal_normalized = text_orginal_normalized.replace("- ", "")






	text_processed_normalized=text_processed_normalized.strip()
	text_orginal_normalized=text_orginal_normalized.strip()


	# split the words into  list
	text_orginal_normalized_split = text_orginal_normalized.split(" ")
	text_processed_normalized_split = text_processed_normalized.split(" ")

	testcoiunter = 0

	orginal_text_index = 0
	process_text_index = 0

	longest = len(text_processed_normalized_split) -1

	if len(text_processed_normalized_split) > len(text_orginal_normalized_split):
		longest = len(text_orginal_normalized_split) -1


	diffs = []
	# for index, word in enumerate(text_processed_normalized_split):
	# we just need to loop for enough number of times to make it through the longest version of the doc
	c =0
	for x in range(0,longest):

		# we'll be maintaining two seperate indexs to keep track of where we are in the two files
		orginal_text_index = orginal_text_index + 1
		process_text_index = process_text_index + 1

		# does the current index exist in both texts?
		if 0 <= orginal_text_index < len(text_orginal_normalized_split) and 0 <= process_text_index < len(text_processed_normalized_split):


			# the indexes might be at two different points in the doc but the words they are currently on should match up
			# if they dont that is an issue so we need to document that and then get the indexs to align again correctly

			if text_orginal_normalized_split[orginal_text_index] == text_processed_normalized_split[process_text_index]:

				print (text_orginal_normalized_split[orginal_text_index], "==", text_processed_normalized_split[process_text_index])

			else:

				#they don't match for some reason, either the word is different or the word is missing

				# we need to document it first
				orginal_text_example_start_index = orginal_text_index - 10
				# the orgianl text sentence example
				if orginal_text_example_start_index < 0:
					orginal_text_example_start_index = 0

				orginal_text_example_end_index = orginal_text_index + 10
				if orginal_text_example_end_index > len(text_orginal_normalized_split) - 1:
					orginal_text_example_end_index = len(text_orginal_normalized_split) - 1


				orginal_example_sentence = text_orginal_normalized_split[orginal_text_example_start_index:orginal_text_example_end_index]
				orginal_example_sentence_bad_index = orginal_text_index - orginal_text_example_start_index

				orginal_example_sentence[orginal_example_sentence_bad_index] = "*"+orginal_example_sentence[orginal_example_sentence_bad_index]+"*"

				processed_text_example_start_index = process_text_index - 10
				if processed_text_example_start_index < 0:
					processed_text_example_start_index = 0

				processed_text_example_end_index = process_text_index + 10
				if processed_text_example_end_index > len(text_processed_normalized_split) - 1:
					processed_text_example_end_index = len(text_processed_normalized_split) - 1

				processed_example_sentence = text_processed_normalized_split[processed_text_example_start_index:processed_text_example_end_index]
				processed_example_sentence_bad_index = process_text_index - processed_text_example_start_index

				processed_example_sentence[processed_example_sentence_bad_index] = "*"+processed_example_sentence[processed_example_sentence_bad_index]+"*"

				
				diffs.append({
					"id": c,
					"orginal_text": " ".join(orginal_example_sentence),
					"processed_text": " ".join(processed_example_sentence),
					"orginal_text_array": orginal_example_sentence,
					"processed_text_array": processed_example_sentence
				})
				c = c + 1

				# its documented now we need to see if we can find new common words to sync up on together
				# we will check 1, 2, 3..5 words if we need to
				break_loop=False
				for look_next_word_increase_by in range(0,5):

					# check based off the processed text first
					next_processed_word = text_processed_normalized_split[process_text_index+look_next_word_increase_by]

					print("lookign for ",next_processed_word,flush=True)
					for modified_orginal_text_index in range(orginal_text_index, orginal_text_index+5):

						# if len(text_orginal_normalized_split) == modified_orginal_text_index:
						# 	print("We are at the end of the orginal text, breaking out of the loop",flush=True)
						# 	break_loop=True
						# 	break

						try:
							test = text_orginal_normalized_split[modified_orginal_text_index]
						except:
							continue

						print(len(text_orginal_normalized_split),modified_orginal_text_index,flush=True)
						print(text_orginal_normalized_split[modified_orginal_text_index],flush=True	)
						print("---------------",flush=True)



						if text_orginal_normalized_split[modified_orginal_text_index] == next_processed_word:
							print("Found it at index", modified_orginal_text_index)
							orginal_text_index = modified_orginal_text_index
							process_text_index = process_text_index+look_next_word_increase_by

							print("SEtting org index to:", text_orginal_normalized_split[orginal_text_index])
							print("processed index set to:", text_processed_normalized_split[process_text_index])
							break_loop=True
							break

					if break_loop:
						break




				# testcoiunter=testcoiunter+1
				# if testcoiunter >5:
				# 	break

		else:

			print("Error we are on index orginal_text_index:", orginal_text_index, "and process_text_index:",process_text_index, "And that is longer than one of them!")





		# # it exists in the orginal text
		# if len(text_orginal_normalized_split) -1 >= index+new_index_offset:

		# 	if text_orginal_normalized_split[index+new_index_offset] == text_processed_normalized_split[index]:

		# 		print(text_orginal_normalized_split[index+new_index_offset],"==",text_processed_normalized_split[index])
		# 		pass # okay
		# 	else:
		# 		print(text_orginal_normalized_split[index+new_index_offset],"!=",text_processed_normalized_split[index])

		# 		start_at_word = index - 10
		# 		if start_at_word < 0:
		# 			start_at_word = 0

		# 		end_at_word = index + 10
		# 		if end_at_word > len(text_processed_normalized_split)-1:
		# 			end_at_word=len(text_processed_normalized_split)-1

		# 		processed_example_sentence_bad_index = index - start_at_word

		# 		processed_example_sentence = text_processed_normalized_split[start_at_word:end_at_word]
		# 		print(processed_example_sentence)
		# 		print(processed_example_sentence_bad_index)


		# 		# -- build the example sentence from the orginal
		# 		end_at_word = index+new_index_offset + 10
		# 		if end_at_word > len(text_orginal_normalized_split)-1:
		# 			end_at_word=len(text_orginal_normalized_split)-1

		# 		orginal_example_sentence = text_orginal_normalized_split[start_at_word:end_at_word]


		# 		print(" ".join(orginal_example_sentence))
		# 		print(" ".join(processed_example_sentence))

		# 		# look ahead X number of words to see if we can sync back up at a specific index
		# 		c=0
		# 		for look_ahead_index in list(range(index+new_index_offset,index+new_index_offset+20)):
		# 			print(look_ahead_index)
		# 			if look_ahead_index > len(text_orginal_normalized_split)-1:
		# 				break

		# 			c=c+1
		# 			if text_orginal_normalized_split[look_ahead_index] == text_processed_normalized_split[index+1]:
		# 				print("Found a new sync!", text_orginal_normalized_split[look_ahead_index])
		# 				new_index_offset = new_index_offset + c
		# 				break




		# 		# break



		# # it does not exist in the text
		# else:

		# 	pass






	# print(len(text_orginal_normalized))
	# print(len(text_processed_normalized))

	# with open("Test.txt",'w') as outfile:
	# 	outfile.write(text_orginal_normalized + "\n")
	# 	outfile.write(text_processed_normalized + "\n")

	return diffs

# 


# 

# 	print(match, len(match.split(" ")))