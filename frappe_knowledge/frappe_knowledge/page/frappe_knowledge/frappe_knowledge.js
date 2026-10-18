frappe.pages["frappe-knowledge"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Frappe Knowledge"),
		single_column: true,
	});
	const project = page.add_field({
		fieldname: "project",
		label: __("Project"),
		fieldtype: "Link",
		options: "FK Project",
	});
	const snapshot = page.add_field({
		fieldname: "snapshot",
		label: __("Snapshot"),
		fieldtype: "Link",
		options: "FK Snapshot",
		get_query: () => ({ filters: { project: project.get_value() } }),
	});
	const query = page.add_field({
		fieldname: "query",
		label: __("Find dependencies"),
		fieldtype: "Data",
	});
	project.$input.on("change", () => snapshot.set_value(""));
	const result = $("<div></div>").appendTo(page.main);
	$("<p></p>")
		.text(
			__(
				"Inspect versioned source evidence. This prototype provides static context; runtime behavior still needs verification."
			)
		)
		.appendTo(result);
	page.add_inner_button(__("Index installed sources"), async () => {
		const projectId = project.get_value();
		if (!projectId) {
			result.empty().append($("<p></p>").text(__("Select a project.")));
			return;
		}
		result.empty().append($("<p></p>").text(__("Queueing a local source scan...")));
		try {
			const response = await frappe.call({
				method: "frappe_knowledge.ingest.request_local_index",
				args: { project: projectId },
			});
			result
				.empty()
				.append(
					$("<p></p>").text(
						__(
							"Local indexing queued. It may take several minutes. Reopen the snapshot selector after it finishes."
						)
					)
				);
			$("<p></p>")
				.text(__("Job ID: ") + response.message.job_id)
				.appendTo(result);
		} catch (error) {
			result
				.empty()
				.append(
					$("<p></p>").text(
						__(
							"Unable to queue local indexing. Check the project and your permissions."
						)
					)
				);
		}
	});
	page.set_primary_action(__("Find context"), async () => {
		const projectId = project.get_value();
		const snapshotId = snapshot.get_value();
		const question = query.get_value();
		if (!projectId) {
			result.empty().append($("<p></p>").text(__("Select a project.")));
			return;
		}
		if (!snapshotId) {
			result.empty().append($("<p></p>").text(__("Select a snapshot.")));
			return;
		}
		if (!question) {
			result.empty().append($("<p></p>").text(__("Enter a question.")));
			return;
		}
		result.empty().append($("<p></p>").text(__("Loading context...")));
		try {
			const response = await frappe.call({
				method: "frappe_knowledge.api.get_context",
				args: { snapshot: snapshotId, query: question, max_chars: 16000 },
				freeze: true,
			});
			result.empty();
			// Render source and questions as text, never as executable HTML.
			$("<pre></pre>")
				.css({ "white-space": "pre-wrap", "overflow-wrap": "anywhere" })
				.text(JSON.stringify(response.message, null, 2))
				.appendTo(result);
		} catch (error) {
			result.empty().append($("<p></p>").text(__("Unable to load context. Please retry.")));
		}
	});
};
