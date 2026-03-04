var portalId = prompt("Enter the source instance id/app id");
var failedSolutionIdsToGet = [];
var failedSolutionIdsToUpload = [];
var solutionsMap = new Map();
var inlineImages = 0;
var attachmetsCount = 0;
async function getDataUriSameOrigin(imageUrl) {
	try {
		const response = await fetch(imageUrl);
		if (!response.ok) { return null; }
		const blob = await response.blob();
		return new Promise((resolve, reject) => {
			const reader = new FileReader();
			reader.onloadend = () => resolve(reader.result);
			reader.onerror = reject;
			reader.readAsDataURL(blob);
		});
	} catch (error) {
		console.error("Error fetching image:", error);
		return null;
	}
}

async function createFileFromURL(url, filename, mimeType) {
	try {
		const response = await fetch(url);
		if (!response.ok) {
			throw new Error("Failed to fetch URL: ${response.status} ${response.statusText}");
		}
		const blob = await response.blob();
		return new File([blob], filename, { type: mimeType });
	} catch (error) {
		console.error("Error creating File from URL:", error);
		return null;
	}
}

async function solutionPost(solutionData, newDec, solutions, index) {
	var newAttachments = [];
	function solutionAdd() {
		let displayId = solutionData.solution.display_id.value;
		delete solutionData.solution.display_id;
		delete solutionData.solution.id
		jQuery.sdpapi.post({
			url: "/solutions",
			data: getAsInputData(solutionData),
			callback: function(response, issuccess) {
				if (!issuccess) {
					failedSolutionIdsToUpload.push(displayId);
				} else {
					solutionsMap.set(displayId, response.solution.display_id.value);
				}
				uploadSolution(solutions, index)
			}
		})
	}

	async function duplicateAttachments(attachmentIndex) {
		if (attachmentIndex < solutionData.solution.attachments.length) {
			var oldAttachment = solutionData.solution.attachments[attachmentIndex];
			var imageURL = "/app/" + portalId + "/api/v3" + oldAttachment.content_url;
			createFileFromURL(imageURL, oldAttachment.name, oldAttachment.content_type).then(file => {
				if (file) {
					var fdata = new FormData();
					fdata.append('filename', file);
					loadAjaxURL({
						type: "POST",
						url: "/api/v3/solutions/_uploads",
						contentType: false,
						context: document.body,
						data: fdata,
						ignore_encryption: true,
						processData: false,
						headers: { 'Accept': 'application/vnd.manageengine.v3+json', 'X-ZCSRF-TOKEN': csrfParamName + '=' + csrfParamValue },
						success: function(data) {
							attachmetsCount++;
							newAttachments.push({ "file_id": data.files[0].file_id })
							duplicateAttachments(++attachmentIndex);

						},
						error: function() {
							duplicateAttachments(++attachmentIndex);
						}
					});
				} else {
					duplicateAttachments(++attachmentIndex);
				}
			});
		} else {
			solutionData.solution.attachments = newAttachments;
			solutionAdd();
		}

	}

	if (solutionData) {
		var fieldsToDelete = ["public_comment_count", "private_comment_count", "last_updated_by", "latest_version", "draft",
			"likes", "created_time", "dislikes", "created_by", "last_updated_time", "no_of_hits", "deleted_time", "has_user_group", "user_group_mapping",
			"has_technician_group", "technician_group_mapping"];
		sdpEach(fieldsToDelete, function(key, value) {
			delete solutionData.solution[value];
		});

		solutionData.solution.topic = {name : solutionData.solution.topic.name};
		delete solutionData.solution.approval_status.id;
		delete solutionData.solution.template.id;
		delete solutionData.response_status;
		var currentDate = new Date();
		currentDate.setHours(24, 0, 0, 0);
		nextDay = currentDate.getTime();
		if (solutionData.solution.review_date && parseInt(solutionData.solution.review_date.value) < nextDay) {
			delete solutionData.solution.review_date;
		}
		if (solutionData.solution.expiry_date && parseInt(solutionData.solution.expiry_date.value) < nextDay) {
			delete solutionData.solution.expiry_date;
		}
		newDec ? (solutionData.solution.description = newDec) : "";
		let attachLength = solutionData.solution.attachments.length;
		if (attachLength > 0) {
			if (attachmetsCount + attachLength > 95) {
				console.log("waiting for a minute for attachments" + attachmetsCount, attachLength);
				inlineImages = 0;
				attachmetsCount = 0;
				setTimeout(function() {
					duplicateAttachments(0);
				}, 60000);

			} else {
				duplicateAttachments(0);
			}

		} else {
			solutionAdd();
		}

	} else {
		uploadSolution(solutions, index)
	}
}

function getAllSolutions(startIndex, rowcount) {
	jQuery.sdpapi.get({
		url: "/solutions",
		headers: { 'x-sdpod-appid': portalId }, //No I18N
		data: getAsInputData({ "list_info": { "start_index": startIndex, "row_count": rowcount, "fields_required": ["id"], "get_total_count": true } }),
		callback: function(response, issuccess) {
			if (issuccess) {
				uploadSolution(response.solutions, 0);
			}
		}
	})
}

function uploadSolution(solutions, index) {
	if (index < solutions.length) {
		jQuery.sdpapi.get({
			url: "/solutions/" + solutions[index].id,
			headers: { 'x-sdpod-appid': portalId }, //No I18N
			callback: async function(solutionData, issuccess) {
				if (issuccess) {


					var desc = solutionData.solution.description;
					const parser = new DOMParser();
					const doc = parser.parseFromString(desc, 'text/html');
					const images = doc.querySelectorAll('img');

					var doUpload = async function() {
						const uploadPromises = Array.from(images).map(async (img) => {
							return getDataUriSameOrigin(img.src).then(async dataUri => {
								if (dataUri) {
									img.src = await uploadImageURI(dataUri);
									inlineImages++;
									return img.src;
								} else {
									img.remove();
									return "";
								}
							});

						});

						const uploadedUrls = (await Promise.all(uploadPromises)).filter(url => typeof url === 'string');

						if (uploadedUrls.length > 0) {
							solutionPost(solutionData, doc.body.innerHTML, solutions, ++index);
						}

					}

					if (images.length > 0) {
						if (inlineImages + images.length > 18) {
							console.log("waiting for a minute for Inline" + inlineImages, images.length);
							inlineImages = 0;
							attachmetsCount = 0;
							setTimeout(doUpload, 60000);

						} else {
							doUpload();
						}
					} else {
						solutionPost(solutionData, undefined, solutions, ++index);
					}
				} else {
					solutionPost(undefined, undefined, solutions, ++index);
					failedSolutionIdsToGet.push(solutions[index].id);
				}
			}
		})
	} else {
		console.log("total no of solutions migrated : ", solutions.length - failedSolutionIdsToGet.length - failedSolutionIdsToUpload.length);
		console.log("Failed solutions list to GET : ", failedSolutionIdsToGet);
		console.log("Failed solutions list to upload : ", failedSolutionIdsToUpload);
		console.log("solutions map Old instance to new : ", solutionsMap);
	}
}

getAllSolutions(1, 100);