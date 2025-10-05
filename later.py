# class EntryRevision(models.Model):
#     """Track changes to troubleshooting entries"""

#     entry = models.ForeignKey(
#         TroubleshootingEntry, on_delete=models.CASCADE, related_name="revisions"
#     )
#     revised_by = models.ForeignKey(User, on_delete=models.CASCADE)
#     title = models.CharField(max_length=200)
#     problem_description = models.TextField()
#     solution = models.TextField()
#     change_summary = models.CharField(max_length=200, blank=True)
#     revision_number = models.PositiveIntegerField()
#     created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         unique_together = ["entry", "revision_number"]
#         ordering = ["-revision_number"]

#     # Inside EntryRevision model
#     def save(self, *args, **kwargs):
#         if not self.pk:  # Only on creation
#             latest_revision = (
#                 EntryRevision.objects.filter(entry=self.entry)
#                 .order_by("-revision_number")
#                 .first()
#             )
#             if latest_revision:
#                 self.revision_number = latest_revision.revision_number + 1
#             else:
#                 self.revision_number = 1
#         super().save(*args, **kwargs)

#     def __str__(self):
#         return f"Revision {self.revision_number} for {self.entry.title} by {self.revised_by.username}"


# class Attachment(models.Model):
#     ATTACHMENT_TYPES = [
#         ("IMAGE", "Image"),
#         ("DOCUMENT", "Document"),
#         ("VIDEO", "Video"),
#         ("AUDIO", "Audio"),
#         ("ARCHIVE", "Archive"),
#         ("OTHER", "Other"),
#     ]

#     troubleshooting_entry = models.ForeignKey(
#         TroubleshootingEntry, on_delete=models.CASCADE, related_name="attachments"
#     )
#     file = models.FileField(
#         upload_to="troubleshooting_attachments/%Y/%m/",
#         validators=[
#             FileExtensionValidator(
#                 allowed_extensions=[
#                     "jpg",
#                     "jpeg",
#                     "png",
#                     "gif",
#                     "pdf",
#                     "txt",
#                     "doc",
#                     "docx",
#                     "xls",
#                     "xlsx",
#                     "mp4",
#                     "avi",
#                     "mov",
#                     "mp3",
#                     "wav",
#                     "zip",
#                     "rar",
#                 ]
#             )
#         ],
#     )
#     original_filename = models.CharField(max_length=255)
#     file_type = models.CharField(max_length=10, choices=ATTACHMENT_TYPES)
#     file_size = models.PositiveIntegerField()  # in bytes
#     mime_type = models.CharField(max_length=100)
#     description = models.CharField(max_length=200, blank=True)

#     # Image-specific fields
#     uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
#     uploaded_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         ordering = ["uploaded_at"]

#     def get_file_type_from_mime(self, mime_type):
#         mime_mappings = {
#             'image/': 'IMAGE',
#             'application/pdf': 'DOCUMENT',
#             'text/': 'DOCUMENT',
#             'video/': 'VIDEO',
#             'audio/': 'AUDIO',
#             'application/zip': 'ARCHIVE',
#             'application/x-rar': 'ARCHIVE',
#         }
    
#         for mime_prefix, file_type in mime_mappings.items():
#             if mime_type.startswith(mime_prefix) or mime_type == mime_prefix:
#                 return file_type
#         return 'OTHER'

#     def clean(self):
#         super().clean()
#         if self.file:
#             if self.file.size > 10 * 1024 * 1024:
#                 raise ValidationError("File size must be under 10MB")

#             self.file.seek(0)
#             self._detected_mime = magic.from_buffer(self.file.read(2048), mime=True)
#             self.file.seek(0)

#             try:
#                 detected_mime = magic.from_buffer(self.file.read(2048), mime=True)
#             except Exception as e:
#                 raise ValidationError(f"Could not determine file type using magic: {e}")
#             self.file.seek(0)

#             allowed_mimes = {
#                 'IMAGE': ['image/jpeg', 'image/png', 'image/gif'],
#                 'DOCUMENT': ['application/pdf', 'text/plain', 
#                             'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
#                 'VIDEO': ['video/mp4', 'video/x-msvideo', 'video/quicktime'],
#                 'AUDIO': ['audio/mpeg', 'audio/wav'],
#                 'ARCHIVE': ['application/zip', 'application/x-rar-compressed'],
#             }
            

#             if detected_mime not in allowed_mimes:
#                 raise ValidationError(f"File type '{detected_mime}' is not allowed.")

        
#             self.original_filename = self.file.name
#             self.file_size = self.file.size
#             self.mime_type = detected_mime
#             self.file_type = self._get_file_type_from_mime(detected_mime)    

#     def save(self, *args, **kwargs):
#         # if self.file and not self.pk:
#         #     self.original_filename = self.file.name
#         #     self.file_size = self.file.size
            
#         #     # Use MIME type detected in clean() if available
#         #     if hasattr(self, '_detected_mime'):
#         #         self.mime_type = self._detected_mime
#         #     else:
#         #         self.file.seek(0)
#         #         self.mime_type = magic.from_buffer(self.file.read(2048), mime=True)
#         #         self.file.seek(0)
            
#         #     self.file_type = self.get_file_type_from_mime(self.mime_type)
        
#         super().save(*args, **kwargs)


#     def __str__(self):
#         return f"{self.original_filename} ({self.troubleshooting_entry.title})"


# class Vote(models.Model):
#     VOTE_TYPES = [
#         ("UP", "Upvote"),
#         ("DOWN", "Downvote"),
#     ]

#     troubleshooting_entry = models.ForeignKey(
#         TroubleshootingEntry, on_delete=models.CASCADE, related_name="votes"
#     )
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     vote_type = models.CharField(max_length=4, choices=VOTE_TYPES)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         unique_together = ["troubleshooting_entry", "user"]
#         indexes = [
#             models.Index(fields=["troubleshooting_entry", "vote_type"]),
#         ]


#     def save(self, *args, **kwargs):
#         super().save(*args, **kwargs)
#         self.update_vote_counts()

#     def delete(self, *args, **kwargs):
#         entry_id = self.troubleshooting_entry_id
#         super().delete(*args, **kwargs)
#         self.update_vote_counts(entry_id)


#     @classmethod
#     def update_vote_counts(cls, entry_id=None):
#         queryset = TroubleshootingEntry.objects.all()
#         if entry_id:
#             queryset = queryset.filter(pk=entry_id)

#         # Use a more advanced annotation to calculate score in one go
#         queryset.annotate(
#             calculated_score=Sum(
#                 models.Case(
#                     models.When(votes__vote_type='UP', then=Value(1)),
#                     models.When(votes__vote_type='DOWN', then=Value(-1)),
#                     default=Value(0),
#                     output_field=IntegerField()
#                 )
#             ),
#             calculated_upvotes=Count('votes', filter=Q(votes__vote_type='UP'))
#         ).update(
#             vote_score=F('calculated_score'),
#             upvotes_count=F('calculated_upvotes')
#         )

# class SoftDeleteManager(models.Manager):
#     def get_queryset(self):
#         return SoftDeleteQuerySet(self.model, using=self._db).active()
    


# class SoftDeleteModel(models.Model):
#     is_deleted = models.BooleanField(default=False)
#     deleted_at = models.DateTimeField(null=True, blank=True)

#     objects = SoftDeleteManager() # Default manager
#     all_objects = models.Manager() # Manager to get all items, including deleted

#     def delete(self):
#         self.is_deleted = True
#         self.deleted_at = timezone.now()
#         self.save()
    
#     def restore(self):
#         self.is_deleted = False
#         self.deleted_at = None
#         self.save()
        
#     class Meta:
#         abstract = True



# class Comment(MPTTModel, SoftDeleteModel):
#     troubleshooting_entry = models.ForeignKey(
#         TroubleshootingEntry, on_delete=models.CASCADE, related_name="comments"
#     )
#     parent = models.ForeignKey(
#         "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies"
#     )
#     author = models.ForeignKey(User, on_delete=models.CASCADE)
#     content = models.TextField()
#     is_solution = models.BooleanField(
#         default=False
#     )  # Mark if this comment provides an alternative solution

#     is_edited = models.BooleanField(default=False)

#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     # Hierarchy
#     # path = models.CharField(max_length=255, unique=True)  # For ltree implementation
#     # level = models.PositiveIntegerField(default=0)  # For depth tracking

#     class MPTTMeta:
#         ordering = ["created_at"]

#     def __str__(self):
#         return (
#             f"Comment by {self.author.username} on {self.troubleshooting_entry.title}"
#         )



# class SoftDeleteQuerySet(models.QuerySet):
#     def delete(self):
#         return super().update(is_deleted=True, deleted_at=timezone.now())
    
#     def active(self):
#         return self.filter(is_deleted=False)

